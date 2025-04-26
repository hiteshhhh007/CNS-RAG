# 🚀 RAG-Based Cryptography & Network Security Chatbot with S3,Ollama & Langchain 🧠

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) 

**A powerful, self-hosted Conversational AI demonstrating Retrieval-Augmented Generation (RAG) using local LLMs via Ollama, vector storage with ChromaDB, and seamless document integration from AWS S3.**

This application provides a web-based chat interface where users can interact with Large Language Models (LLMs) whose knowledge is augmented by documents stored in an AWS S3 bucket. It's specifically configured with prompts tailored for cryptography discussions but can be adapted for various domains. The system automatically keeps the knowledge base synchronized with the S3 bucket content.

---

## ✨ Features

*   **AWS S3 Integration:** Loads documents directly from a specified S3 bucket.
*   **Automatic S3 Synchronization:**
    *   Checks for new, updated (based on S3 Version ID), and deleted files on startup.
    *   Processes and embeds new/updated files into the vector store.
    *   Removes data related to deleted S3 files from the vector store.
*   **Real-time File Upload:** Upload supported documents (`.pdf`, `.ppt`, `.pptx`) directly through the web UI, which are added to S3 and immediately embedded.
*   **Retrieval-Augmented Generation (RAG):** Uses Langchain to orchestrate the RAG pipeline:
    *   Retrieves relevant text chunks from documents stored in ChromaDB based on user queries.
    *   Injects retrieved context into the LLM prompt.
*   **Local LLM Support via Ollama:** Leverages locally running LLMs (configurable, `qwen2.5:7b`, `deepseek-r1:7b`) through Ollama for generation and reasoning, ensuring data privacy.
*   **Vector Store:** Uses ChromaDB to store document embeddings (vectors) locally for efficient similarity search.
*   **Conversational Memory:** Maintains conversation history per user session for context-aware interactions.
*   **Streaming Responses:** Provides a smooth chat experience by streaming the LLM's response token by token.
*   **Configurable Models:** Easily switch between a default LLM and a potentially more powerful "reasoning" LLM via a query parameter.
*   **Modular Code Structure:** Organized into separate modules for configuration, S3 handling, vector store operations, and Flask routes for better maintainability.

---

## 🛠️ Technology Stack

*   **Backend:** Python, Flask
*   **AI/ML Orchestration:** Langchain
*   **LLMs:** Ollama ( Qwen2.5:7b, deepseek-r1:7b)
*   **Embeddings:** Ollama (Nomic Embed Text)
*   **Vector Database:** ChromaDB
*   **Cloud Storage:** AWS S3 (via Boto3)
*   **Frontend:** HTML, Tailwind-CSS, JavaScript (using Server-Sent Events for streaming)
*   **Document Loading:** PyPDFLoader, UnstructuredFileLoader (for PPT/PPTX)

---

## 📁 Directory Structure
```
CNS-RAG/
├── app.py                                   # Main Flask application: routes, initialization orchestration
├── config.py                                # All configuration constants (Models, S3, Paths, etc.)
├── s3_handler.py                            # Functions specifically for S3 interactions (list, download, upload)
├── vectorstore_handler.py                   # Manages ChromaDB, Langchain setup, document processing, S3 sync logic
├── utils.py                                 # General utility functions (e.g., allowed_file)
├── templates/
│ └── index.html                             # Frontend HTML structure
├── static/
│ └── js/
│ └── chat.js                                # Frontend JavaScript for chat logic, SSE, file upload
├── chroma_db/                               # (Created automatically by ChromaDB on first run/sync)
├── requirements.txt                         # Python dependencies
├── .env                                     # Environment variables (AWS keys, secrets - DO NOT COMMIT)
├── .gitignore                               # Specifies intentionally untracked files (like .env, chroma_db)
└── README.md                                                                  
```

## ⚙️ Prerequisites

Before you begin, ensure you have the following installed and configured:

1.  **Python:** Version 3.9 or higher.
2.  **pip:** Python package installer.
3.  **Git:** For cloning the repository.
4.  **AWS Account:** An active AWS account.
5.  **AWS Credentials:** Configured for Boto3. The easiest ways are:
    *   **Environment Variables:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`.
    *   **Shared Credential File:** `~/.aws/credentials`.
    *   **IAM Role:** If running on EC2/ECS/EKS.
    *   *Ensure the credentials have necessary permissions for your S3 bucket (ListBucket, GetObject, PutObject, GetObjectVersion, HeadObject, ListBucketVersions).*
6.  **AWS S3 Bucket:** An existing S3 bucket where your source documents reside or will be uploaded. **Versioning must be enabled** on the bucket for the update detection logic to work correctly.
7.  **Ollama:** Installed and running locally. Download from [ollama.com](https://ollama.com/).
8.  **Ollama Models Pulled:** Ensure the LLM and embedding models specified in `config.py` (or your `.env` overrides) are downloaded:
    ```bash
    ollama pull qwen2.5:7b   # Default LLM (or your configured default)
    ollama pull deepseek-r1:7b # Default Reasoning LLM (or your configured one)
    ollama pull nomic-embed-text # Default Embedding model (or your configured one)
    ```
9.  **Optional System Dependencies:** `unstructured` library might require system packages for processing certain file types (like `.ppt`/`.pptx`). Check the [Unstructured documentation](https://unstructured-io.github.io/unstructured/installing.html) for details (e.g., `libreoffice` might be needed).

---

## 🚀 Setup & Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/hiteshhhh007/CNS-RAG.git
    cd CNS-RAG
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    # Linux/macOS
    python3 -m venv venv
    source venv/bin/activate

    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(This may take some time, especially for libraries like `unstructured`)*

4.  **Configure Environment Variables:**
    *   Create a file named `.env` in the project root directory.
    *   Copy the contents from the example below and **modify them with your actual values**.

    **.env Example Template:**
    ```ini
    # .env - DO NOT COMMIT THIS FILE TO GIT!

    # --- Flask Configuration ---
    # Generate a strong random key: python -c 'import secrets; print(secrets.token_hex(24))'
    FLASK_SECRET_KEY='YOUR_VERY_STRONG_FLASK_SECRET_KEY'
    # FLASK_DEBUG=False # Set to True for development, False for production

    # --- AWS Credentials (If not using ~/.aws/credentials or IAM Role) ---
    # AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY
    # AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_KEY
    AWS_DEFAULT_REGION=ap-south-1 # IMPORTANT: Set to your S3 bucket's region

    # --- S3 Configuration ---
    S3_BUCKET_NAME=your-actual-s3-bucket-name # Replace with your bucket name
    # S3_PREFIX=docs/ # Optional: Uncomment and set if your files are in a specific folder within the bucket

    # --- Model Names (Optional Overrides - Defaults are in config.py) ---
    # DEFAULT_LLM_MODEL=qwen2.5:7b
    # REASONING_LLM_MODEL=deepseek-r1:7b
    # EMBEDDING_MODEL=nomic-embed-text
    ```

    **⚠️ Security:** Ensure your `.env` file is listed in your `.gitignore` file and **never commit it** to version control.

5.  **Ensure Ollama is Running:** Start the Ollama application/service if it's not already running. Verify the required models are available (`ollama list`).

---

## ▶️ Running the Application

1.  **Navigate to the Project Root:** Make sure you are in the `CNS-RAG` directory where `app.py` resides and your virtual environment is activated.

2.  **Start the Flask Server:**
    ```bash
    python app.py
    ```

3.  **First Run & Initialization:**
    *   On the very first run (or if the `chroma_db` directory doesn't exist), the application will:
        *   Connect to your S3 bucket.
        *   List all files in the configured `S3_BUCKET_NAME` (and `S3_PREFIX` if set).
        *   Download, process, and embed each document.
        *   Create the `chroma_db` directory and store the embeddings.
    *   On subsequent runs, it will:
        *   Load the existing `chroma_db`.
        *   Perform the S3 synchronization check (add new, update changed, remove deleted).
    *   This initial indexing might take time depending on the number and size of your documents. Monitor the console output for progress.

4.  **Access the Chat Interface:** Open your web browser and navigate to:
    `http://127.0.0.1:5000` (or the host/port shown in the console output).

---

## 💬 Usage

1.  **Chat:** Type your message in the input box and press Enter or click Send. The chatbot will respond, potentially using information from your S3 documents.
2.  **Sources:** If the response uses information from your documents, source links (clickable S3 URLs) might appear below the response.
3.  **File Upload:** Click the "Upload File" button, select a supported file (`.pdf`, `.ppt`, `.pptx`), and upload. The file will be sent to S3 and indexed automatically. You should see console logs indicating the process. *(Note: A page refresh might be needed for the file list/chat to immediately use the new content, depending on frontend implementation details).*
4.  **Reasoning Model:** If your frontend (`chat.js`) includes a toggle or if you manually adjust the `/chat` endpoint call, you can switch between the default and reasoning LLMs (e.g., by adding `?use_reasoning=true` to the GET request to `/chat`).
5.  **New Session:** Use the "New Session" button to clear the current conversation history.

---

## Architecture Diagram
```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'fontSize': '13px', 'primaryColor': '#F5F5F5', 'primaryTextColor': '#333', 'lineColor': '#666', 'secondaryColor': '#D2E7FF', 'tertiaryColor': '#FFF4CC'}}}%%
graph TD
    subgraph "Legend"
        direction TB
        L_User[fa:fa-user User]
        L_Browser[fa:fa-window-maximize Browser HTML/JS]
        L_Flask[fa:fa-server Flask Backend app.py]
        L_Config[fa:fa-cog Configuration config.py/.env]
        L_S3H[fa:fa-code S3 Handler s3_handler.py]
        L_VSH[fa:fa-database Vector Store Handler vectorstore_handler.py]
        L_S3B[fa:fa-aws AWS S3 Bucket]
        L_Chroma[fa:fa-database ChromaDB Local]
        L_Ollama[fa:fa-brain Ollama Local LLM/Embeddings]
        L_LC[fa:fa-link Langchain]
    end

    subgraph "1. Initialization Flow On App Start"
        direction TB
        Start(Start Flask App `python app.py`) --> ReadConfig[Read config.py / .env];
        ReadConfig --> InitS3Client[Flask calls S3 Handler: Init S3 Client];
        InitS3Client --> InitEmbed[Flask calls VS Handler: Init Embeddings Model];
        InitEmbed -- Uses --> O_Embed(Ollama Embeddings);
        InitEmbed --> InitVS[Flask calls VS Handler: Initialize Vector Store];

        InitVS --> CheckDB{ChromaDB Exists?};

        CheckDB -- No / Force Rebuild --> S3List1[VS Handler calls S3 Handler: List S3 Files/Versions];
        S3List1 -- Reads --> S3B1(fa:fa-aws AWS S3 Bucket);
        S3List1 --> ProcessLoop(Loop: Each S3 File);
        ProcessLoop --> S3Download1[VS Handler calls S3 Handler: Download File];
        S3Download1 -- Reads --> S3B1;
        S3Download1 --> LoadSplit1[VS Handler: Load & Split Document];
        LoadSplit1 --> CreateDB[VS Handler: Create ChromaDB w/ Embeddings];
        CreateDB -- Uses --> O_Embed;
        CreateDB --> Persist1[VS Handler: Persist ChromaDB];
        Persist1 --> InitDone[Initialization Complete];

        CheckDB -- Yes --> LoadDB[VS Handler: Load Existing ChromaDB];
        LoadDB --> GetDBMeta[VS Handler: Get Metadata from ChromaDB];
        GetDBMeta --> S3List2[VS Handler calls S3 Handler: List S3 Files/Versions];
        S3List2 -- Reads --> S3B2(fa:fa-aws AWS S3 Bucket);
        S3List2 --> Compare[VS Handler: Compare S3 vs DB Metadata];
        Compare --> IdentifyChanges[Identify New / Updated / Deleted];
        IdentifyChanges --> DeleteOld{Need Deletions?};
        DeleteOld -- Yes --> QueryDeleteIDs[VS Handler: Query ChromaDB for IDs to Delete];
        QueryDeleteIDs --> DeleteChunks[VS Handler: Delete Chunks from ChromaDB];
        DeleteChunks --> ProcessNewUpdated{Need Processing?};
        DeleteOld -- No --> ProcessNewUpdated;

        ProcessNewUpdated -- Yes New/Updated --> ProcessLoop2(Loop: Each New/Updated File);
        ProcessLoop2 --> S3Download2[VS Handler calls S3 Handler: Download File];
        S3Download2 -- Reads --> S3B2;
        S3Download2 --> LoadSplit2[VS Handler: Load & Split Document];
        LoadSplit2 --> AddChunks[VS Handler: Add New/Updated Chunks w/ Embeddings];
        AddChunks -- Uses --> O_Embed;
        AddChunks --> ChangesMade{DB Changed?};
        ProcessNewUpdated -- No --> ChangesMade;


        ChangesMade -- Yes --> Persist2[VS Handler: Persist ChromaDB];
        Persist2 --> InitDone;
        ChangesMade -- No --> InitDone;
    end


    subgraph "2. Chat Interaction Flow"
        direction TB
        User(fa:fa-user User) -- Types message --> Browser(fa:fa-window-maximize Browser);
        Browser -- GET /chat message, history --> Flask(fa:fa-server Flask Backend);
        Flask -- Loads history --> Session[Flask Session];
        Flask --> GetChain[Flask calls VS Handler: Get Chat Chain];
        GetChain -- Initializes --> LChain(fa:fa-link Langchain ConversationalRetrievalChain);
        LChain -- Uses --> O_LLM_Chat(Ollama LLM);
        LChain -- Uses --> O_Embed_Chain(Ollama Embeddings via Chroma);
        LChain -- Reads --> ChromaDB1(fa:fa-database ChromaDB);

        Flask -- Calls chain.stream --> RAG[RAG Process via Langchain];
        subgraph "RAG Process Langchain"
            direction TB
             RAG_Start(Start Streaming) --> CondenseQ[1. Condense Question];
             CondenseQ -- Uses --> O_LLM_RAG1(Ollama LLM);
             CondenseQ --> Retrieve[2. Retrieve Docs];
             Retrieve -- Query Vector Store --> ChromaDB_RAG(fa:fa-database ChromaDB);
             Retrieve --> Combine[3. Combine Docs & Generate Answer];
             Combine -- Uses --> O_LLM_RAG2(Ollama LLM);
             Combine --> RAG_End(Stream Answer Chunks);
        end
        RAG --> Flask;
        Flask -- Streams SSE data, sources, end --> Browser;
        Flask -- Updates history --> Session;
        Browser -- Updates UI --> User;
    end

    subgraph "3. File Upload Flow"
        direction TB
        User_Up(fa:fa-user User) -- Selects & Uploads File --> Browser_Up(fa:fa-window-maximize Browser);
        Browser_Up -- POST /upload_file file --> Flask_Up(fa:fa-server Flask Backend);
        Flask_Up --> Validate[Flask: Validate File];
        Validate --> UploadS3[Flask calls S3 Handler: Upload to S3];
        UploadS3 -- Writes --> S3B_Up(fa:fa-aws AWS S3 Bucket);
        UploadS3 --> GetMeta[Flask calls S3 Handler: Get S3 Metadata VersionID];
        GetMeta -- Reads --> S3B_Up;
        GetMeta --> ProcessS3Obj[Flask calls VS Handler: Process S3 Object];
        ProcessS3Obj -- Calls --> S3Download_Up[S3 Handler: Download Temp File];
        S3Download_Up -- Reads --> S3B_Up;
        S3Download_Up --> LoadSplit_Up[VS Handler: Load & Split Document];
        ProcessS3Obj --> DeleteCheck{Delete Old Chunks?};
        DeleteCheck -- Yes --> DeleteOld_Up[VS Handler: Delete Chunks from ChromaDB];
        DeleteCheck -- No --> AddNew_Up;
        DeleteOld_Up --> AddNew_Up[VS Handler: Add New Chunks w/ Embeddings];
        AddNew_Up -- Uses --> O_Embed_Up(Ollama Embeddings via Chroma);
        AddNew_Up --> Persist_Up[VS Handler: Persist ChromaDB];
        Persist_Up --> Resp[Flask: Send Success/Error Response];
        Resp --> Browser_Up;
        Browser_Up -- Displays status --> User_Up;
    end

    %% Styling Optional
    classDef default fill:#F9F9F9,stroke:#BBB,stroke-width:1px,color:#333;
    classDef process fill:#D2E7FF,stroke:#87CEEB,stroke-width:1px,color:#000;
    classDef storage fill:#FFF4CC,stroke:#FFD700,stroke-width:1px,color:#333;
    classDef external fill:#E8D5E8,stroke:#9370DB,stroke-width:1px,color:#000;
    classDef decision fill:#FFDAB9,stroke:#FFA07A,stroke-width:1px,color:#000;
    classDef io fill:#90EE90,stroke:#3CB371,stroke-width:1px,color:#000;

    class User,User_Up io;
    class Browser,Browser_Up io;
    class Flask,Flask_Up process;
    class S3H,L_S3H process;
    class VSH,L_VSH process;
    class InitS3Client,InitEmbed,InitVS,ProcessLoop,S3Download1,LoadSplit1,CreateDB,Persist1,LoadDB,GetDBMeta,S3List1,S3List2,Compare,IdentifyChanges,QueryDeleteIDs,DeleteChunks,ProcessLoop2,S3Download2,LoadSplit2,AddChunks,Persist2,Validate,UploadS3,GetMeta,ProcessS3Obj,S3Download_Up,LoadSplit_Up,DeleteOld_Up,AddNew_Up,Persist_Up process;
    class GetChain,LChain,RAG,RAG_Start,CondenseQ,Retrieve,Combine,RAG_End process;
    class S3B1,S3B2,S3B_Up,L_S3B storage;
    class ChromaDB1,ChromaDB_RAG,L_Chroma storage;
    class Session storage;
    class O_Embed,O_Embed_Chain,O_LLM_Chat,O_LLM_RAG1,O_LLM_RAG2,O_Embed_Up,L_Ollama external;
    class L_LC external;
    class L_User,L_Browser,L_Flask,L_Config,L_S3H,L_VSH,L_S3B,L_Chroma,L_Ollama,L_LC,Start,InitDone,Resp io;
    class CheckDB,DeleteOld,ProcessNewUpdated,ChangesMade,DeleteCheck decision;
```

## 🏗️ How It Works (Architecture Overview)

1.  **Initialization (`initialize_app` in `app.py`):**
    *   Connects to AWS S3.
    *   Initializes the Ollama embedding model.
    *   Calls `vectorstore_handler.initialize_vector_store`.

2.  **Vector Store Initialization/Sync (`initialize_vector_store` in `vectorstore_handler.py`):**
    *   Loads existing ChromaDB or prepares to build a new one.
    *   Lists current objects/versions in S3 (`s3_handler.list_s3_objects_versions`).
    *   **If Building:** Processes all S3 files (`vectorstore_handler.process_s3_object`), creates ChromaDB (`Chroma.from_documents`), persists.
    *   **If Loading:** Loads ChromaDB (`Chroma(...)`), gets metadata of stored files (`get_processed_files_from_db`), compares with S3 list.
    *   **Sync Logic:**
        *   Identifies new, updated (version mismatch), and deleted S3 files.
        *   Deletes chunks for updated/deleted files from ChromaDB (`vs.delete`).
        *   Processes new/updated files (`process_s3_object`).
        *   Adds new chunks to ChromaDB (`vs.add_documents`).
        *   Persists changes (`vs.persist`).

3.  **Chat Request (`/chat` route in `app.py`):**
    *   Receives user message and reasoning flag.
    *   Retrieves conversation history from the Flask session.
    *   Calls `vectorstore_handler.get_chat_chain` to get a Langchain `ConversationalRetrievalChain` instance configured for the request (with history and selected LLM).
    *   Streams the chain's response back to the frontend using SSE.

4.  **Langchain RAG Pipeline (`get_chat_chain` in `vectorstore_handler.py`):**
    *   **Condense Question:** An LLMChain uses conversation history and the new question to create a standalone query suitable for retrieval.
    *   **Retrieve:** The ChromaDB vector store is queried using the standalone question to find relevant document chunks.
    *   **Combine Docs:** The retrieved chunks are formatted and stuffed into a context variable.
    *   **Generate Answer:** Another LLMChain takes the original question, chat history, and the retrieved context, feeding them to the final LLM prompt (QA_PROMPT) to generate the answer.
    *   The `ConversationalRetrievalChain` manages this flow.

5.  **File Upload (`/upload_file` route in `app.py`):**
    *   Receives the file from the frontend.
    *   Uploads the file to S3 (`s3_handler.upload_to_s3`).
    *   Gets the new S3 object's metadata (VersionID).
    *   Calls `vectorstore_handler.process_s3_object` to download, process, and chunk the *just uploaded* file.
    *   Deletes any existing chunks for the *same file key* in ChromaDB.
    *   Adds the new chunks to ChromaDB.
    *   Persists the changes.

---

## 🔧 Customization

*   **Models:** Change LLM and embedding models in `config.py` or via `.env` variables. Remember to pull the new models using Ollama.
*   **Prompts:** Modify the `QA_PROMPT_TEMPLATE` and `CONDENSE_QUESTION_PROMPT_TEMPLATE` in `vectorstore_handler.py` to change the chatbot's persona, instructions, or reasoning process.
*   **RAG Strategy:** Adjust retriever settings (`k` value, search type) in `get_chat_chain` within `vectorstore_handler.py`. Explore different Langchain chains or document combination methods (e.g., MapReduce, Refine).
*   **Text Splitting:** Modify `CHUNK_SIZE` and `CHUNK_OVERLAP` in `config.py`.
*   **Supported File Types:** Extend `ALLOWED_EXTENSIONS` in `config.py` and ensure the corresponding `Langchain` document loader is implemented in `_load_and_split_document` (`vectorstore_handler.py`). You might need additional `unstructured` extras (`pip install "unstructured[filetype]"`).
*   **S3 Configuration:** Update bucket name, prefix, and region in `.env` or `config.py`.

---

## ⚠️ Troubleshooting

*   **AWS Credentials Error:** Ensure your AWS credentials are correctly configured and have the necessary S3 permissions. Check `~/.aws/credentials`, environment variables, or IAM role policies. Verify the `AWS_DEFAULT_REGION` in `.env` matches your bucket's region.
*   **Ollama Connection Refused/Model Not Found:** Make sure the Ollama service is running and that you have pulled the specific models defined in your configuration (`ollama list`).
*   **S3 Bucket Not Found/Access Denied:** Double-check the `S3_BUCKET_NAME` in `.env`. Verify bucket permissions and that versioning is enabled.
*   **`unstructured` Errors:** Document processing might fail if `unstructured` lacks system dependencies (like `libreoffice` for `.ppt`). Consult the `unstructured` installation guide.
*   **Slow Indexing/Chat:** Processing large documents or using large LLMs on less powerful hardware can be slow. Consider optimizing chunk sizes or using smaller models if performance is an issue.
*   **Force Rebuild:** If the ChromaDB seems corrupted or out of sync, stop the application, delete the `chroma_db` directory, and restart the application to trigger a full rebuild from S3.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Happy Chatting!* 🎉
