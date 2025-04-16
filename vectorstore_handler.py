# vectorstore_handler.py
import os
import shutil
import tempfile
import traceback
from datetime import datetime

# Langchain and related imports
from langchain_community.vectorstores import Chroma
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain.schema.output_parser import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredFileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema.runnable import RunnablePassthrough
from langchain.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
# from langchain.chains.question_answering import load_qa_chain # Not explicitly used in the final chain setup
from langchain.chains.llm import LLMChain
from langchain.chains.combine_documents.stuff import StuffDocumentsChain # Used directly
from langchain_core.messages import HumanMessage, AIMessage

# Local imports
import config # Import our configuration
import s3_handler # Import S3 functions

# --- Module-level globals for shared resources ---
vector_store = None
embeddings = None

# --- Initialization Functions ---

def get_embeddings_model():
    """Initializes and returns the embeddings model, caching it globally."""
    global embeddings
    if embeddings is None:
        print("  Initializing Ollama embeddings model...")
        try:
            # Use model name from config
            embeddings = OllamaEmbeddings(model=config.EMBEDDING_MODEL)
            print(f"  Embeddings model '{config.EMBEDDING_MODEL}' initialized.")
        except Exception as e:
            print(f"  FATAL ERROR initializing embeddings model '{config.EMBEDDING_MODEL}': {e}")
            traceback.print_exc()
            return None # Return None on failure
    return embeddings

def get_vector_store():
    """Returns the initialized vector store instance."""
    global vector_store
    # This function assumes initialize_vector_store was successfully called beforehand
    if vector_store is None:
         print("WARNING: get_vector_store() called before initialization.")
    return vector_store

# --- Document Loading and Processing ---

def _load_and_split_document(local_file_path, s3_key, version_id, last_modified):
    """
    Loads a document from a *local* file path, adds S3 metadata, and splits it into chunks.
    Handles different file types (PDF, TXT, PPT/PPTX via Unstructured).
    """
    docs = []
    try:
        _, file_extension = os.path.splitext(s3_key)
        file_extension = file_extension.lower()

        print(f"    Loading document: {os.path.basename(local_file_path)} (from S3 key: {s3_key})")
        loader = None
        if file_extension == ".pdf":
            loader = PyPDFLoader(local_file_path)
        elif file_extension == ".txt":
            loader = TextLoader(local_file_path, encoding='utf-8')
        # Add ppt/pptx handling using UnstructuredFileLoader
        elif file_extension in ['.ppt', '.pptx']:
             print(f"    Using UnstructuredFileLoader for {file_extension}")
             # You might need to install specific extras like `pip install "unstructured[pptx]"`
             loader = UnstructuredFileLoader(local_file_path, mode="elements") # Or try mode="single"
        else:
            # Fallback for other types UnstructuredFileLoader might handle
            print(f"    Warning: Attempting to load unsupported file type '{file_extension}' with UnstructuredFileLoader as fallback.")
            try:
                loader = UnstructuredFileLoader(local_file_path)
            except Exception as e:
                print(f"    Error creating UnstructuredFileLoader for {local_file_path}: {e}")
                return [] # Cannot load this file type

        if loader:
            loaded_docs = loader.load()
        else: # Should not happen if logic above is correct, but as safeguard
             print(f"    Error: No suitable loader found for file extension {file_extension}")
             return []


        if not loaded_docs:
             print(f"    Warning: No documents loaded from {local_file_path}. The file might be empty or corrupted.")
             return []

        print(f"    Splitting document: {s3_key}")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            length_function=len,
            add_start_index=True # Good for context/debugging
        )

        # Add metadata BEFORE splitting
        public_url = s3_handler.construct_public_s3_url(s3_key)
        iso_last_modified = last_modified.isoformat() if last_modified else None

        for doc in loaded_docs:
            # Ensure metadata dictionary exists and is modifiable
            if not hasattr(doc, 'metadata') or doc.metadata is None:
                doc.metadata = {}
            elif not isinstance(doc.metadata, dict): # If it exists but isn't a dict
                 print(f"Warning: Document metadata is not a dict, attempting to convert for {s3_key}. Original: {doc.metadata}")
                 # Try to preserve existing info if possible, otherwise overwrite
                 try: doc.metadata = dict(doc.metadata)
                 except: doc.metadata = {} # Overwrite if conversion fails

            # Add our standard metadata keys
            doc.metadata[config.S3_KEY_METADATA_KEY] = s3_key
            doc.metadata[config.S3_VERSION_ID_METADATA_KEY] = version_id
            doc.metadata[config.S3_URL_METADATA_KEY] = public_url
            # Keep 'source' consistent as many Langchain components expect it
            doc.metadata[config.SOURCE_METADATA_KEY] = public_url
            doc.metadata[config.LAST_MODIFIED_S3_METADATA_KEY] = iso_last_modified
            # Preserve original source if loader provided one, otherwise use S3 URL
            if 'source' not in doc.metadata:
                 doc.metadata['source'] = public_url # Default source if loader didn't add one


        doc_chunks = text_splitter.split_documents(loaded_docs)
        print(f"    Split into {len(doc_chunks)} chunks.")
        return doc_chunks

    except Exception as e:
        print(f"    ERROR processing local document {local_file_path} (from S3 key {s3_key}): {e}")
        traceback.print_exc() # Print detailed traceback for debugging
        return [] # Return empty list on error

def process_s3_object(s3_client, s3_key, version_id, last_modified):
    """
    Downloads a single S3 object to a temporary location,
    then calls _load_and_split_document to load, process, and split it.
    Returns a list of Document chunks.
    """
    # Create a safe local filename from the S3 key
    safe_local_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in os.path.basename(s3_key))
    if not safe_local_filename: # Handle case where basename is empty or only invalid chars
        safe_local_filename = f"s3_dl_{version_id or 'unknown'}"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(temp_dir, safe_local_filename)

        # Download the file from S3
        download_ok = s3_handler.download_s3_object(
            s3_client, config.S3_BUCKET_NAME, s3_key, temp_file_path
        )

        if download_ok:
            # If download succeeded, process the local file
            return _load_and_split_document(temp_file_path, s3_key, version_id, last_modified)
        else:
            # If download failed, log it and return empty list
            print(f"  Skipping processing for s3://{config.S3_BUCKET_NAME}/{s3_key} due to download failure.")
            return []

# --- Vector Store Management ---

def get_processed_files_from_db(vs):
    """
    Retrieves a dictionary mapping S3 keys to their last processed VersionIDs
    by querying the metadata of all documents in the ChromaDB instance.
    """
    processed = {}
    if not vs:
        print("  Vector store not available for metadata query.")
        return processed
    try:
        print("  Querying ChromaDB for existing S3 metadata...")
        # Fetch only metadata, specify the keys needed for efficiency if possible
        # `include=["metadatas"]` fetches all metadata fields for each document
        results = vs.get(include=["metadatas"]) # Gets all entries

        count = 0
        s3_keys_found = set()
        if results and results.get('metadatas') and results.get('ids'):
            if len(results['ids']) == 0:
                 print("  ChromaDB exists but contains no documents.")
                 return processed

            print(f"  Scanning metadata of {len(results['ids'])} chunks in DB...")
            for metadata in results['metadatas']:
                s3_key = metadata.get(config.S3_KEY_METADATA_KEY)
                version_id = metadata.get(config.S3_VERSION_ID_METADATA_KEY)

                # Ensure both key and version_id are present in the metadata
                if s3_key and version_id:
                    # Store the version ID associated with the key.
                    # If a key somehow has multiple versions stored (shouldn't happen with correct update logic),
                    # this will store the version ID from the *last* chunk encountered for that key.
                    # The update logic relies on deleting *all* chunks for a key before adding the new ones.
                    processed[s3_key] = version_id
                    s3_keys_found.add(s3_key)
                    count += 1
                # Log if essential metadata is missing from a chunk (indicates potential issue)
                # elif s3_key:
                #     print(f"    Warning: Chunk metadata for S3 key '{s3_key}' is missing '{config.S3_VERSION_ID_METADATA_KEY}'.")
                # else:
                #     # This case is less likely if documents are added correctly
                #     print(f"    Warning: Found chunk metadata missing '{config.S3_KEY_METADATA_KEY}'. Metadata: {metadata}")


            print(f"  Found metadata for {len(s3_keys_found)} unique S3 keys across {count} relevant chunk entries in DB.")
        else:
            # This case handles an empty DB or if the .get() call fails unexpectedly
            print("  No documents or metadata found in ChromaDB.")
    except Exception as e:
        print(f"  WARNING: Error fetching or processing metadata from ChromaDB: {e}")
        traceback.print_exc()
        # Return potentially partial results, but log the error. Sync might be incomplete.
    return processed

def initialize_vector_store(force_rebuild=False):
    """
    Initializes the Chroma vector store.
    - Checks if a local DB exists.
    - Handles forced rebuilds by deleting the existing DB.
    - If no DB exists or rebuild forced: builds a new DB from all current S3 objects.
    - If DB exists: loads it.
    - Performs an S3 synchronization:
        - Finds new files in S3 -> processes and adds them.
        - Finds updated files in S3 -> deletes old chunks, processes new version, adds new chunks.
        - Finds files deleted from S3 -> deletes corresponding chunks from DB.
    - Persists changes.
    - Sets the module-level `vector_store` variable.
    - Returns the Chroma instance or exits fatally on critical errors.
    """
    global vector_store, embeddings
    print("\n--- Initializing Vector Store ---")

    # 1. Ensure Embeddings Model is ready
    embeddings = get_embeddings_model()
    if not embeddings:
        print("  FATAL: Could not initialize embeddings model. Exiting.")
        exit(1)

    # 2. Ensure S3 Client is ready (needed for build/sync)
    s3_client = s3_handler.get_s3_client()
    if not s3_client:
        print("  FATAL: Could not initialize S3 client. Exiting.")
        exit(1)

    # 3. Handle DB Path and Rebuild Logic
    vs = None
    db_path = config.CHROMA_PATH
    db_exists = os.path.exists(db_path) and os.path.isdir(db_path)

    if force_rebuild and db_exists:
        print(f"  Force Rebuild Requested: Deleting existing Chroma DB at '{db_path}'")
        try:
            shutil.rmtree(db_path)
            db_exists = False
            print("  Existing DB deleted successfully.")
        except OSError as e:
            print(f"  FATAL ERROR deleting existing Chroma DB: {e}. Please remove manually and restart.")
            exit(1)

    # 4. Build New DB or Load Existing One
    if not db_exists:
        # --- Build New DB from S3 ---
        print(f"  No DB found at '{db_path}' or rebuild forced. Performing full initial load from S3...")
        # List current files/versions in S3
        s3_objects_info = s3_handler.list_s3_objects_versions(s3_client, config.S3_BUCKET_NAME, config.S3_PREFIX)
        all_chunks = []
        if not s3_objects_info:
            print(f"  WARNING: No files found in s3://{config.S3_BUCKET_NAME}/{config.S3_PREFIX}. Initializing an empty DB.")
            # Create an empty DB instance if bucket is empty
            try:
                 vs = Chroma(embedding_function=embeddings, persist_directory=db_path)
                 # Need to explicitly persist to create the directory structure
                 vs.persist()
                 print(f"  Empty vector store created and persisted at '{db_path}'")
            except Exception as e:
                 print(f"  FATAL ERROR creating empty Chroma DB: {e}")
                 traceback.print_exc()
                 exit(1)
        else:
             # Process all found S3 objects
             print(f"  Processing {len(s3_objects_info)} S3 objects for initial embedding...")
             file_count = 0
             processed_chunks_count = 0
             for s3_key, info in s3_objects_info.items():
                 print(f"  Processing {s3_key} (Version: {info.get('VersionId', 'N/A')})...")
                 chunks = process_s3_object(s3_client, s3_key, info.get('VersionId'), info.get('LastModified'))
                 if chunks:
                     all_chunks.extend(chunks)
                     file_count += 1
                     processed_chunks_count += len(chunks)
                 else:
                      print(f"    Warning: Failed to process or get chunks for {s3_key}. It will not be included in the initial build.")

             # Create Chroma DB from the collected chunks
             if not all_chunks:
                  print("  WARNING: No documents could be successfully processed from S3. Creating an empty DB.")
                  try:
                     vs = Chroma(embedding_function=embeddings, persist_directory=db_path)
                     vs.persist()
                     print(f"  Empty vector store created and persisted at '{db_path}'")
                  except Exception as e:
                     print(f"  FATAL ERROR creating empty Chroma DB after processing failure: {e}")
                     traceback.print_exc()
                     exit(1)
             else:
                  print(f"\n  Creating new Chroma vector store with {processed_chunks_count} chunks from {file_count} successfully processed files...")
                  try:
                      vs = Chroma.from_documents(
                          documents=all_chunks,
                          embedding=embeddings, # Pass the initialized embeddings function
                          persist_directory=db_path
                      )
                      vs.persist() # Persist after creation
                      print(f"  Vector store created with initial data and persisted at '{db_path}'")
                  except Exception as e:
                      print(f"  FATAL ERROR creating new Chroma DB from documents: {e}")
                      traceback.print_exc()
                      exit(1)
        # No S3 sync needed immediately after a full build
        needs_s3_sync = False

    else:
        # --- Load Existing DB ---
        print(f"  Loading existing Chroma vector store from '{db_path}'...")
        try:
            vs = Chroma(persist_directory=db_path, embedding_function=embeddings)
            # Simple check to see if it loaded something
            count = vs._collection.count()
            print(f"  Vector store loaded successfully with {count} existing chunks.")
            needs_s3_sync = True # Need to sync after loading
        except Exception as e:
            # Includes errors like directory not found, invalid metadata, etc.
            print(f"  FATAL ERROR loading existing Chroma DB from '{db_path}': {e}")
            print("  Consider deleting the directory and letting the script rebuild, or investigate the error.")
            traceback.print_exc()
            exit(1) # Exit if loading fails

    # 5. S3 Synchronization (if DB was loaded, not newly built)
    if vs and needs_s3_sync:
        print("\n--- Starting S3 Synchronization Check ---")
        processed_db_info = get_processed_files_from_db(vs) # Get {s3_key: versionId} from DB
        current_s3_info = s3_handler.list_s3_objects_versions(s3_client, config.S3_BUCKET_NAME, config.S3_PREFIX) # Get {s3_key: {VersionId, LastModified}} from S3

        chunks_to_add = []
        keys_to_remove_chunks_for = set() # Collect all S3 keys whose chunks need deletion (updated or deleted)
        new_files_processed = 0
        updated_files_processed = 0
        processed_keys_in_db = set(processed_db_info.keys())
        current_keys_in_s3 = set(current_s3_info.keys())

        # Identify New and Updated Files
        print("  Checking for new or updated files in S3...")
        for s3_key, s3_info in current_s3_info.items():
            current_version_id = s3_info.get('VersionId')
            last_modified = s3_info.get('LastModified')
            stored_version_id = processed_db_info.get(s3_key)

            if s3_key not in processed_db_info:
                # File is in S3 but not in DB -> New file
                print(f"    + New file detected: {s3_key}")
                new_chunks = process_s3_object(s3_client, s3_key, current_version_id, last_modified)
                if new_chunks:
                    chunks_to_add.extend(new_chunks)
                    new_files_processed += 1
                else:
                    print(f"      Warning: Failed to process new file {s3_key}, it will not be added.")
            elif current_version_id != stored_version_id:
                # File is in S3 and DB, but VersionID differs -> Updated file
                print(f"    * Updated file detected: {s3_key} (S3 Ver: {current_version_id}, DB Ver: {stored_version_id})")
                # Mark this key for deletion of old chunks FIRST
                keys_to_remove_chunks_for.add(s3_key)
                # Process the updated file
                updated_chunks = process_s3_object(s3_client, s3_key, current_version_id, last_modified)
                if updated_chunks:
                    chunks_to_add.extend(updated_chunks) # Add new chunks later
                    updated_files_processed += 1
                else:
                    # If processing the update fails, DON'T delete the old version chunks.
                    print(f"      Warning: Failed to process updated file {s3_key}. Old version chunks will NOT be removed, and the update will NOT be added.")
                    keys_to_remove_chunks_for.discard(s3_key) # Remove from deletion list
            # else: File exists in both and version matches -> No action needed

        # Identify Deleted Files
        print("  Checking for files deleted from S3...")
        keys_deleted_from_s3 = processed_keys_in_db - current_keys_in_s3
        if keys_deleted_from_s3:
            print(f"    - {len(keys_deleted_from_s3)} file(s) deleted from S3 detected:")
            for key in keys_deleted_from_s3:
                print(f"      - {key}")
            # Mark these keys for chunk removal as well
            keys_to_remove_chunks_for.update(keys_deleted_from_s3)
        else:
            print("    No files found deleted from S3.")

        # --- Perform DB Modifications ---
        db_changed = False

        # 6. Deletions (Perform first)
        if keys_to_remove_chunks_for:
            print(f"\n  Removing chunks for {len(keys_to_remove_chunks_for)} updated/deleted S3 keys...")
            ids_to_delete = []
            try:
                # Build a ChromaDB 'where' filter to find all chunks associated with these keys
                # Example using $or or iterating if $in isn't directly supported for metadata keys in older versions
                # Using where filter which is standard:
                where_filter = {config.S3_KEY_METADATA_KEY: {"$in": list(keys_to_remove_chunks_for)}}

                # Get the IDs of the documents matching the filter
                print(f"    Querying for chunk IDs to delete with filter: {where_filter}...")
                existing_data = vs.get(where=where_filter, include=[]) # Only need IDs, not content/metadata

                if existing_data and existing_data.get('ids'):
                    ids_to_delete = existing_data['ids']
                    if ids_to_delete:
                        print(f"    Deleting {len(ids_to_delete)} chunk IDs...")
                        vs.delete(ids=ids_to_delete)
                        print("    Deletion successful.")
                        db_changed = True
                    else:
                        # This case might happen if keys were marked but chunks were already gone somehow
                        print("    No matching chunk IDs found for deletion (might have been deleted previously).")
                else:
                    print("    No existing chunks found for keys marked for deletion.")
            except Exception as e:
                print(f"    WARNING: Error querying or deleting old chunks: {e}. Some outdated data might remain.")
                traceback.print_exc()
        else:
            print("\n  No chunks require deletion.")


        # 7. Additions (Perform after deletions)
        if chunks_to_add:
            print(f"\n  Adding {len(chunks_to_add)} new/updated chunks to ChromaDB...")
            try:
                # Add documents in batches if list is very large (Chroma handles reasonably large lists well)
                # batch_size = 500
                # for i in range(0, len(chunks_to_add), batch_size):
                #     batch = chunks_to_add[i:i + batch_size]
                #     vs.add_documents(batch)
                #     print(f"    Added batch {i//batch_size + 1}...")
                # Simpler addition for typical cases:
                vs.add_documents(chunks_to_add)
                print("  Addition successful.")
                db_changed = True
            except Exception as e:
                print(f"    WARNING: Error adding new/updated chunks to ChromaDB: {e}")
                print(f"    Some processed files might not be available for search. Consider re-sync or rebuild if errors persist.")
                traceback.print_exc()
        else:
             print("\n  No new or updated chunks require adding.")


        # 8. Persist Changes (if any deletions or additions occurred)
        if db_changed:
            print("\n  Persisting ChromaDB changes...")
            try:
                vs.persist()
                print("  ChromaDB changes persisted successfully.")
            except Exception as e:
                print(f"  WARNING: Failed to persist ChromaDB changes: {e}")
                traceback.print_exc()
        else:
            print("\n  No changes made to ChromaDB during sync.")

        print(f"\n--- S3 Synchronization Summary ---")
        print(f"  New files processed: {new_files_processed}")
        print(f"  Updated files processed: {updated_files_processed}")
        print(f"  Files deleted from S3: {len(keys_deleted_from_s3)}")
        print(f"  Chunks added: {len(chunks_to_add)}")
        print(f"  S3 Keys whose chunks were removed: {len(keys_to_remove_chunks_for)}")
        print(f"--- S3 Synchronization Complete ---")

    elif not vs:
        # This case should ideally be caught earlier by exit(1)
        print("  Skipping S3 sync as vector store initialization failed earlier.")


    # 9. Final Assignment and Return
    if not vs:
        print("\nFATAL ERROR: Vector store could not be initialized or loaded after all steps.")
        exit(1)

    vector_store = vs # Assign to the module global
    print("\n--- Vector Store Initialization Complete ---")
    return vector_store # Return the instance for the main app


# --- Chat Chain Creation ---

def get_chat_chain(vs, llm_model_name, chat_history_messages):
    """
    Creates and returns a ConversationalRetrievalChain instance for handling chat requests.

    Args:
        vs: The initialized Chroma vector store instance.
        llm_model_name: The name of the Ollama model to use (e.g., config.DEFAULT_LLM_MODEL).
        chat_history_messages: A list of Langchain BaseMessage objects representing the conversation history.

    Returns:
        A configured ConversationalRetrievalChain instance, or None if an error occurs.
    """
    print(f"\n  Creating LangChain chat chain with model: {llm_model_name}...")
    if not vs:
        print("  ERROR: Vector store is not available for chain creation.")
        return None # Cannot create chain without vector store

    # 1. Initialize LLM
    try:
        print(f"    Initializing LLM: {llm_model_name}")
        # Adjust temperature or other parameters as needed
        llm = ChatOllama(model=llm_model_name, temperature=0.2)
    except Exception as e:
         print(f"  ERROR: Failed to initialize LLM '{llm_model_name}': {e}")
         traceback.print_exc()
         return None

    # 2. Initialize Memory (Request-Specific)
    # The memory object stores the history *for this specific request's chain*.
    # It's populated with the history passed from the user's session.
    print("    Initializing ConversationBufferMemory...")
    memory = ConversationBufferMemory(
        memory_key='chat_history',
        return_messages=True, # Important for passing history correctly to prompts
        output_key='answer' # Must match the final output key of the chain
    )
    # Load the history provided for this request
    memory.chat_memory.messages = chat_history_messages
    print(f"    Memory loaded with {len(chat_history_messages)} messages.")


    # 3. Initialize Retriever
    print("    Initializing Retriever from vector store...")
    try:
        # Configure retriever (e.g., number of documents 'k')
        retriever = vs.as_retriever(
            search_type="similarity", # Or "mmr", "similarity_score_threshold"
            search_kwargs={'k': 5} # Retrieve top 5 relevant chunks
            )
    except Exception as e:
         print(f"  ERROR: Failed to create retriever from vector store: {e}")
         traceback.print_exc()
         return None

    # 4. Define Prompts

    # Prompt to format individual retrieved documents
    print("    Defining document prompt...")
    DOCUMENT_PROMPT = PromptTemplate.from_template(
        # Use the metadata key configured for the S3 URL
        f"DOCUMENT: {{page_content}}\nSOURCE: {{{config.S3_URL_METADATA_KEY}}}"
    )

    # Prompt for the QA step, combining context, history, and question
    print("    Defining main QA prompt...")
    # Using the detailed template from the original app.py
    QA_PROMPT_TEMPLATE = """You are a helpful AI assistant with expertise in cryptography. You're having a conversation with a human user.

IMPORTANT INSTRUCTIONS:

1) ANALYZE THE USER'S MESSAGE:
   * Is it a casual greeting/chat (like "hello", "thanks", "how are you")?
   * Is it a question or discussion about cryptography?
   * Is it something else entirely?

2) FOR CASUAL CONVERSATION:
   * Respond naturally and conversationally
   * Do NOT include any citations
   * Be friendly, concise, and engaging
   * Never mention the "context documents" for casual chat

3) FOR CRYPTOGRAPHY QUESTIONS:
   * First check if the provided CONTEXT DOCUMENTS contain relevant information
   * If they do, base your answer primarily on this information
   * Add citations ONLY when directly using information from the documents
   * Format citations as: [Source: URL] at the end of the relevant sentence (use the URL from the SOURCE field of the document)
   * If the context does not contain the answer, clearly state this and then provide a general response based on your knowledge of cryptography
   * Only cite sources that you actually use information from. Avoid citing unused sources.

4) TONE GUIDELINES:
   * Be conversational and friendly in all responses
   * Avoid overly formal academic language unless answering technical questions
   * Don't overuse citations - only add them when directly referencing document content
   * For simple questions, keep answers concise
   * For complex topics, provide more thorough explanations

Chat History:
{chat_history}

CONTEXT DOCUMENTS:
{context}

User Message: {question}

Your response:"""

    QA_PROMPT = PromptTemplate(
        input_variables=["chat_history", "context", "question"], # Ensure these match the variables used in the template
        template=QA_PROMPT_TEMPLATE,
    )

    # Prompt to condense the user's input and chat history into a standalone question
    print("    Defining condense question prompt...")
    CONDENSE_QUESTION_PROMPT_TEMPLATE = """Given the conversation history and a new input from the user, create a standalone question that captures the user's core intent for information retrieval.

If the new input is a simple greeting, confirmation ("ok", "thanks"), or casual chat that doesn't require retrieving documents, return it unchanged.
If it's a follow-up question related to the topic (e.g., cryptography), reformulate it to be self-contained, incorporating necessary context from the history. Make it suitable for querying a vector database.

Conversation History:
{chat_history}

New Input: {question}

Standalone question (or unchanged input if casual):"""

    CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(CONDENSE_QUESTION_PROMPT_TEMPLATE)

    # 5. Construct the Chain Components

    # LLM Chain to generate the standalone question
    print("    Building question generator chain...")
    question_generator_chain = LLMChain(
        llm=llm,
        prompt=CONDENSE_QUESTION_PROMPT,
        verbose=False # Set to True for debugging this step
        )

    # LLM Chain to answer the question using the formatted context
    print("    Building answer generation chain...")
    answer_chain = LLMChain(
        llm=llm,
        prompt=QA_PROMPT,
        verbose=False # Set to True for debugging this step
        )

    # Chain to stuff the retrieved documents into the QA prompt's context
    print("    Building document combining chain...")
    combine_docs_chain = StuffDocumentsChain(
        llm_chain=answer_chain, # The chain that will process the combined context
        document_prompt=DOCUMENT_PROMPT, # How to format each doc
        document_variable_name="context", # Variable name in QA_PROMPT for stuffed docs
        document_separator="\n\n----------\n\n", # Separator between docs
        verbose=False # Set to True for debugging this step
    )

    # 6. Construct the Final ConversationalRetrievalChain
    print("    Building final ConversationalRetrievalChain...")
    try:
        conversational_chain = ConversationalRetrievalChain(
            retriever=retriever,                  # Component to fetch relevant documents
            question_generator=question_generator_chain, # Component to create standalone question
            combine_docs_chain=combine_docs_chain, # Component to stuff docs and generate answer
            memory=memory,                        # Component to manage chat history (for this request)
            return_source_documents=True,         # Include retrieved source documents in the output
            # return_generated_question=True,     # Optional: Include the condensed question in output for debugging
            output_key='answer',                  # Specifies the key for the final answer in the output dict
            verbose=False                         # Set to True for detailed logging of the entire chain execution
        )
        print("  LangChain ConversationalRetrievalChain created successfully.")
        return conversational_chain # Return the fully assembled chain

    except Exception as e:
         print(f"  ERROR constructing final ConversationalRetrievalChain: {e}")
         traceback.print_exc()
         return None