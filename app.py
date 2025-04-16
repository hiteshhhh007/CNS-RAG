import os
import uuid
import json
import re
import traceback 
from urllib.parse import urlparse
from werkzeug.utils import secure_filename
from flask import (
    Flask, request, Response, jsonify, render_template, session, stream_with_context
)
from langchain_core.messages import HumanMessage, AIMessage

# Import configurations and handlers
import config
import s3_handler
import vectorstore_handler
import utils

# --- Flask App Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = config.APP_SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Check if using the default secret key
config.check_secret_key()

# --- Global variables for shared resources (initialized at startup) ---
app_s3_client = None
app_vector_store = None
app_embeddings = None

# --- Initialization Function (Call this before running the app) ---
def initialize_app():
    """Initializes S3 client and Vector Store."""
    global app_s3_client, app_vector_store, app_embeddings

    print("--- Initializing Application Components ---")
    # Initialize S3 Client (required by vector store init too)
    app_s3_client = s3_handler.get_s3_client()
    if not app_s3_client:
        print("FATAL: S3 Client initialization failed. Cannot start application.")
        exit(1)

    # Initialize Embeddings (required by vector store init)
    # Note: vectorstore_handler manages its own global `embeddings` instance
    app_embeddings = vectorstore_handler.get_embeddings_model()
    if not app_embeddings:
         print("FATAL: Embeddings model initialization failed. Cannot start application.")
         exit(1)

    # Initialize Vector Store (loads/builds DB and syncs with S3)
    # This function now handles S3 client needs internally
    app_vector_store = vectorstore_handler.initialize_vector_store()
    if not app_vector_store:
        print("FATAL: Vector Store initialization failed. Cannot start application.")
        exit(1)

    print("--- Application Components Initialized Successfully ---")


# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the index.html chat interface."""
    print("Route /: Serving index.html")
    if 'chat_history' not in session:
        session['chat_history'] = []
        session['session_id'] = str(uuid.uuid4())
        print(f"  New session started: {session['session_id']}")
    # Always render, session handles state
    return render_template('index.html')

@app.route('/list_files', methods=['GET'])
def list_files_route():
    """Lists files from S3 for display."""
    print("Route /list_files: Request received.")
    if not app_s3_client:
        return jsonify({"error": "S3 service not available"}), 503

    try:
        
        files_list = s3_handler.list_s3_objects_for_display(
            app_s3_client, config.S3_BUCKET_NAME, config.S3_PREFIX
        )
        print(f"Route /list_files: Returning {len(files_list)} files.")
        return jsonify({"files": files_list}), 200
    except Exception as e:
        print(f"Unexpected error in /list_files: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred listing files."}), 500

@app.route('/upload_file', methods=['POST'])
def upload_file_route():
    """Handles file uploads to S3 and immediate embedding."""
    print("Route /upload_file: Received POST request.")

    # --- Check Prerequisites ---
    if not app_s3_client:
        return jsonify({"error": "S3 service not available for upload"}), 503
    if not app_vector_store:
        return jsonify({"error": "Vector database not ready for upload"}), 503
    if not app_embeddings: 
         return jsonify({"error": "Embeddings model not ready"}), 503

    # --- File Validation ---
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if not utils.allowed_file(file.filename):
        print(f"  Error: File type not allowed: {file.filename}")
        return jsonify({"error": f"File type not allowed. Allowed: {', '.join(config.ALLOWED_EXTENSIONS)}"}), 400

    original_filename = secure_filename(file.filename)
    # Construct S3 key using config prefix
    s3_key = os.path.join(config.S3_PREFIX, original_filename).replace("\\", "/")
    # Remove leading slash if prefix is empty, os.path.join might add one
    if s3_key.startswith('/') and not config.S3_PREFIX:
         s3_key = s3_key[1:]

    print(f"  Processing upload for: {original_filename} -> s3://{config.S3_BUCKET_NAME}/{s3_key}")


    # --- Upload and Process ---
    try:
        # 1. Upload to S3
        upload_ok = s3_handler.upload_to_s3(app_s3_client, file, config.S3_BUCKET_NAME, s3_key)
        if not upload_ok:
            
            return jsonify({"error": "Failed to upload file to S3 storage."}), 500

        # 2. Get Metadata (VersionId, LastModified)
        new_version_id, last_modified = s3_handler.get_s3_object_metadata(
            app_s3_client, config.S3_BUCKET_NAME, s3_key
        )
        if not new_version_id:
            print("  WARNING: Could not retrieve VersionId from uploaded S3 object. Update checks might be unreliable.")
            # Proceed, but log the warning

        # 3. Process Locally & Prepare Chunks (Download > Load > Split > Metadata)
        print("  Processing uploaded file for embedding...")
        new_chunks = vectorstore_handler.process_s3_object(
             app_s3_client, s3_key, new_version_id, last_modified
        )

        if not new_chunks:
            print("  Error: Failed to process the uploaded file into chunks after upload.")
            return jsonify({"error": f"File uploaded to S3, but failed during local processing/splitting. Check server logs."}), 500

        # --- Database Operations ---
        print(f"  Updating vector store for key: {s3_key}")

        # 4. Delete Old Chunks (if any exist for this key)

        ids_to_delete = []
        try:
            where_filter = {config.S3_KEY_METADATA_KEY: s3_key}
            existing_data = app_vector_store.get(where=where_filter, include=[])
            if existing_data and existing_data.get('ids'):
                ids_to_delete = existing_data['ids']
                if ids_to_delete:
                    print(f"    Found {len(ids_to_delete)} existing chunk IDs. Deleting old version...")
                    app_vector_store.delete(ids=ids_to_delete)
                    print("    Old chunk deletion successful.")
            else:
                 print("    No existing chunks found for this key (first upload or previous deletion).")
        except Exception as e:
            print(f"    WARNING: Error querying/deleting existing chunks for {s3_key}: {e}. Proceeding to add new chunks.")
            

        # 5. Add New Chunks
        print(f"  Adding {len(new_chunks)} new chunks to ChromaDB...")
        try:
            app_vector_store.add_documents(documents=new_chunks) # Embeddings are implicitly handled by Chroma if initialized with them
            print("  Chunk addition successful.")

            # 6. Persist Changes Immediately
            try:
                print("  Persisting ChromaDB changes after upload...")
                app_vector_store.persist()
                print("  ChromaDB persisted.")
            except Exception as e:
                print(f"  WARNING: Failed to persist ChromaDB changes immediately after upload: {e}")
                

            return jsonify({
                "message": f"File '{original_filename}' uploaded and processed successfully.",
                "filename": original_filename,
                "s3_key": s3_key,
                "s3_url": s3_handler.construct_public_s3_url(s3_key),
                "chunks_added": len(new_chunks)
            }), 201 

        except Exception as e:
            print(f"  ERROR adding new chunks to ChromaDB for {s3_key}: {e}")
            traceback.print_exc()
            return jsonify({"error": f"File uploaded, but failed during embedding/database update: {e}"}), 500

    except Exception as e:
        print(f"  Unexpected error during file upload process for {original_filename}: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred during upload."}), 500


@app.route('/chat', methods=['GET'])
def chat_stream_route():
    """Handles streaming chat responses using Server-Sent Events (SSE)."""
    print(f"\nRoute /chat (SSE): Received GET request.")

    # --- Check Prerequisites ---
    if not app_vector_store:
        print("  Error: Vector store not initialized.")
        def error_stream_vs():
             yield f"event: error\ndata: {json.dumps({'error': 'Chatbot backend (vector store) not ready'})}\n\n"
             yield f"event: end\ndata: {{}}\n\n"
        return Response(error_stream_vs(), mimetype='text/event-stream')

    # --- Get Request Parameters ---
    user_message = request.args.get('message', '').strip()
    use_reasoning_str = request.args.get('use_reasoning', 'false').lower()
    use_reasoning = use_reasoning_str == 'true'

    if not user_message:
        print("  Error: No message provided in query parameters.")
        def error_stream_msg():
             yield f"event: error\ndata: {json.dumps({'error': 'No message provided'})}\n\n"
             yield f"event: end\ndata: {{}}\n\n"
        return Response(error_stream_msg(), mimetype='text/event-stream')

    session_id = session.get('session_id', 'N/A') 
    print(f"  Session {session_id}: Received message: '{user_message[:50]}...', Use Reasoning: {use_reasoning}")


    # --- Generator Function for the Stream ---
    def generate_response_stream(message, reasoning_flag):
        accumulated_answer = ""
        final_sources_data = []
        llm_to_use = ""
        request_complete = False
        chain_created = False
        error_occurred = False

        try:
            # 1. Load History from Session
            history_dicts = session.get('chat_history', [])
            chat_history_messages = [
                HumanMessage(content=msg['content']) if msg.get('type') == 'human' else AIMessage(content=msg['content'])
                for msg in history_dicts
            ]
            print(f"  Session {session_id}: Loaded {len(chat_history_messages)} history messages for chain.")

            # 2. Select LLM and Get Chain
            llm_to_use = config.REASONING_LLM_MODEL if reasoning_flag else config.DEFAULT_LLM_MODEL
            chain = vectorstore_handler.get_chat_chain(app_vector_store, llm_to_use, chat_history_messages)

            if not chain:
                yield f"event: error\ndata: {json.dumps({'error': 'Failed to create chat processing chain.'})}\n\n"
                error_occurred = True
                return 

            chain_created = True
            print(f"  Session {session_id}: Invoking chain.stream() with model {llm_to_use}...")

            # 3. Stream Response from Chain
            full_response_object = {'answer': '', 'source_documents': []} 
            processed_sources = False 

            for chunk in chain.stream({"question": message}):
                
                if "source_documents" in chunk and chunk["source_documents"] and not processed_sources:
                    final_sources = chunk["source_documents"]
                    full_response_object['source_documents'] = final_sources 
                    source_data_for_event = []
                    seen_urls = set()
                    for doc in final_sources:
                        # Use the configured metadata key for the URL
                        url = doc.metadata.get(config.S3_URL_METADATA_KEY)
                        if url and url not in seen_urls:
                            try:
                                filename = os.path.basename(urlparse(url).path) or "Source Document"
                            except:
                                filename = "Source Document" # Fallback
                            source_data_for_event.append({"url": url, "filename": filename})
                            seen_urls.add(url)

                    if source_data_for_event:
                        final_sources_data = source_data_for_event # Store formatted sources for history update
                        yield f"event: sources\ndata: {json.dumps(source_data_for_event)}\n\n"
                        print(f"  Session {session_id}: Sent 'sources' event with {len(source_data_for_event)} unique items.")
                        processed_sources = True # Prevent sending sources again

                # Check for answer chunk
                if "answer" in chunk:
                    answer_chunk = chunk["answer"]
                    if answer_chunk:
                        accumulated_answer += answer_chunk
                        # Send text chunk as 'data' event (default event type)
                        yield f"data: {json.dumps({'chunk': answer_chunk})}\n\n"
                        # Optional small delay for smoother streaming effect on client
                        # import time
                        # time.sleep(0.01)

            # Mark as complete after the stream finishes naturally
            request_complete = True
            print(f"  Session {session_id}: Stream finished. Full Answer Length: {len(accumulated_answer)}")
            full_response_object['answer'] = accumulated_answer

        except Exception as e:
            error_occurred = True
            print(f"  Session {session_id}: ERROR during streaming generation: {e}")
            traceback.print_exc()
            # Send an error event to the client
            yield f"event: error\ndata: {json.dumps({'error': 'An error occurred during response generation.'})}\n\n"
        finally:
            # --- Update Session History (only if successful and got an answer) ---
            if request_complete and accumulated_answer and not error_occurred:
            
                current_history = session.get('chat_history', [])
                current_history.append({"type": "human", "content": message})
                
                ai_message_content = accumulated_answer 
                current_history.append({
                    "type": "ai",
                    "content": ai_message_content,
                    # Optional: store formatted sources with the message
                    # "sources": final_sources_data
                    })
                session['chat_history'] = current_history
                session.modified = True 
                print(f"  Session {session_id}: Updated history with Human message and AI response (length {len(accumulated_answer)}).")
            elif error_occurred:
                print(f"  Session {session_id}: History not updated due to error during generation.")
            elif not accumulated_answer and chain_created:
                 print(f"  Session {session_id}: Stream finished but no answer generated. History not updated.")
            else:
                print(f"  Session {session_id}: Request did not complete successfully or chain failed. History not updated.")


            # --- Send End Signal ---
           
            print(f"  Session {session_id}: Sending 'end' event.")
            yield f"event: end\ndata: {json.dumps({'model_used': llm_to_use if llm_to_use else 'N/A'})}\n\n"
    return Response(stream_with_context(generate_response_stream(user_message, use_reasoning)), mimetype='text/event-stream')


@app.route('/new_session', methods=['POST'])
def new_session_route():
    """Clears the chat history and assigns a new session ID."""
    session_id_before = session.get('session_id', 'N/A')
    history_len_before = len(session.get('chat_history', []))

    # Clear history and generate new session ID
    session.pop('chat_history', None)
    session['chat_history'] = [] 
    session['session_id'] = str(uuid.uuid4()) 
    session.modified = True 

    print(f"Cleared chat history for old session {session_id_before} (had {history_len_before} messages). New session ID: {session['session_id']}")
    return jsonify({"message": "Chat history cleared, new session started."}), 200


# --- Run the App ---
if __name__ == '__main__':
    print("\n--- Starting Flask Application ---")

    # Initialize S3 Client and Vector Store before running the app
    initialize_app()

    
    print("\n--- Starting Flask Development Server ---")
    print(f"Access the chat interface at: http://127.0.0.1:5000 (or your server's IP)")
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "True").lower() in ['true', '1', 'yes']
    print(f"Running in {'DEBUG' if debug_mode else 'PRODUCTION'} mode.")
    app.run(host=host, port=port, debug=debug_mode)
    print("\n--- Flask Application Terminated ---")