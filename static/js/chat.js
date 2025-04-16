document.addEventListener("DOMContentLoaded", () => {
    // --- DOM Elements ---
    const darkModeToggle = document.getElementById('darkModeToggle');
    const modeDropdownBtn = document.getElementById('modeDropdownBtn');
    const modeDropdown = document.getElementById('modeDropdown');
    const modeDropdownIcon = document.getElementById('modeDropdownIcon');
    const currentMode = document.getElementById('currentMode');
    const modeOptions = document.querySelectorAll('.mode-option');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar'); 
    const mobileSidebar = document.getElementById('mobileSidebar');
    const closeMobileSidebar = document.getElementById('closeMobileSidebar');
    const quickTermsToggle = document.getElementById('quickTermsToggle');
    const quickTerms = document.getElementById('quickTerms');
    const quickTermButtons = document.querySelectorAll('.quick-term');
    const messageInput = document.getElementById('messageInput');
    const sendMessageBtn = document.getElementById('sendMessageBtn');
    const reasoningBtn = document.getElementById('reasoningBtn'); 
    const charCount = document.getElementById('charCount');
    const messagesContainer = document.getElementById('messagesContainer');
    const searchModal = document.getElementById('searchModal');
    const closeSearchModal = document.getElementById('closeSearchModal');
    const executeSearchBtn = document.getElementById('executeSearchBtn');
    const searchResults = document.getElementById('searchResults');
    const documentViewerModal = document.getElementById('documentViewerModal');
    const closeDocumentViewer = document.getElementById('closeDocumentViewer');
    const referenceDocBtn = document.getElementById('referenceDocBtn'); 
    const viewAllDocsBtn = document.getElementById('viewAllDocsBtn');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const notification = document.getElementById('notification');
    const notificationMessage = document.getElementById('notificationMessage');
    const exportSessionBtn = document.getElementById('exportSessionBtn');
    const newSessionBtn = document.getElementById('newSessionBtn');
    
    const sidebarDocsContainer = document.getElementById('sidebarDocsContainer');
    const modalDocsContainer = document.getElementById('modalDocsContainer');
    const modalPaginationInfo = documentViewerModal?.querySelector('.modal-pagination-info'); // Get optional pagination info element
    
    const uploadFileBtn = document.getElementById('uploadFileBtn');
    const fileUploadInput = document.getElementById('fileUploadInput');
    // --- Current State ---
    let currentChatMode = 'normal';
    let isDarkMode = localStorage.getItem('darkMode') === 'true';
    let allFetchedFiles = []; 
    let currentSessionStartTime = new Date();
    let eventSource = null; // For SSE connection

    // ***Initialize markdown-it ***
    const md = window.markdownit({
        html: false, 
        xhtmlOut: false,
        breaks: true, 
        linkify: true, 
        typographer: true, 
    });
    // --- End of markdown-it Init ---

    // --- Initialize ---
    function init() {
       
        if (isDarkMode) {
            document.documentElement.classList.add('dark');
            if (darkModeToggle) darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
        } else {
            document.documentElement.classList.remove('dark');
            if (darkModeToggle) darkModeToggle.innerHTML = '<i class="fas fa-moon"></i>';
        }
        updateModeButtonDisplay();
        setupEventListeners();
        if (messageInput) updateCharCount();
        fetchAndDisplayReferenceFiles();
    }

    // --- Setup Event Listeners ---
    function setupEventListeners() {
        // UI Listeners (Dark Mode, Dropdown, Sidebar Toggle, Quick Terms etc.)
        if (darkModeToggle) darkModeToggle.addEventListener('click', toggleDarkMode);
        if (modeDropdownBtn) modeDropdownBtn.addEventListener('click', toggleModeDropdown);
        modeOptions.forEach(option => { 
            option.addEventListener('click', () => {
                const mode = option.getAttribute('data-mode');
                if (mode === 'normal' || mode === 'reasoning') { setChatMode(mode); }
                else if (mode === 'search') { setChatMode(mode); searchModal?.classList.remove('hidden'); /* ... */ }
                modeDropdown?.classList.add('hidden');
                modeDropdownIcon?.classList.remove('rotate-180');
            });
        });
        if (document) document.addEventListener('click', (e) => {
             if (modeDropdownBtn && modeDropdown && !modeDropdownBtn.contains(e.target) && !modeDropdown.contains(e.target)) {  }
        });
        if (sidebarToggle) sidebarToggle.addEventListener('click', () => mobileSidebar?.classList.remove('hidden'));
        if (closeMobileSidebar) closeMobileSidebar.addEventListener('click', () => mobileSidebar?.classList.add('hidden'));
        if (quickTermsToggle) quickTermsToggle.addEventListener('click', toggleQuickTerms);
        quickTermButtons.forEach(btn => {  });

        // Message Input Listeners
        if (messageInput) {
            messageInput.addEventListener('input', updateCharCount);
            messageInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
            messageInput.addEventListener('input', function () { this.style.height = 'auto'; this.style.height = (this.scrollHeight) + 'px'; });
        }
        if (sendMessageBtn) sendMessageBtn.addEventListener('click', sendMessage);
        if (reasoningBtn) reasoningBtn.addEventListener('click', () => setChatMode(currentChatMode === 'reasoning' ? 'normal' : 'reasoning'));

        // Modal Listeners (Search, Document Viewer)
        if (closeSearchModal) closeSearchModal.addEventListener('click', () => searchModal?.classList.add('hidden'));
        if (executeSearchBtn) executeSearchBtn.addEventListener('click', performSearch); // Simulated search
        if (referenceDocBtn) referenceDocBtn.addEventListener('click', () => documentViewerModal?.classList.remove('hidden')); // Keep if using this button
        if (closeDocumentViewer) closeDocumentViewer.addEventListener('click', () => documentViewerModal?.classList.add('hidden'));

        
        if (viewAllDocsBtn) {
            viewAllDocsBtn.addEventListener('click', () => {
                renderModalFiles(allFetchedFiles); 
                if (documentViewerModal) documentViewerModal.classList.remove('hidden');
            });
        }

        // Other UI buttons
        if (exportSessionBtn) exportSessionBtn.addEventListener('click', showExportNotification); // Simulated export
        if (newSessionBtn) newSessionBtn.addEventListener('click', startNewBackendSession); 
       
        if (uploadFileBtn) {
            uploadFileBtn.addEventListener('click', () => {
                fileUploadInput?.click(); // Trigger the hidden file input
            });
        }
        if (fileUploadInput) {
            fileUploadInput.addEventListener('change', handleFileUpload); // Handle file selection
        }
    }

    // --- Core Backend Interaction (sendMessage) ---
    function sendMessage() {
        if (!messageInput) return;
        const message = messageInput.value.trim();
        if (!message) return;

        // Close any existing EventSource connection
        closeEventSource();

        const useReasoning = currentChatMode === 'reasoning';

        // Add user message to UI
        addMessageToChat('user', message);

        // Clear input
        const messageToSend = message; // Keep for potential logging
        messageInput.value = '';
        messageInput.style.height = 'auto';
        updateCharCount();
        messageInput.focus(); // Keep focus on input

        // --- Create the bot message bubble structure immediately ---
        const botMessageId = `bot-msg-${Date.now()}`;
        addMessageToChat('bot-init', '', null, [], null, botMessageId); // Special type

        // Show placeholder/spinner inside the new bubble
        const botContentArea = document.getElementById(botMessageId);
        if (botContentArea) {
             botContentArea.innerHTML = `<p class="generating-placeholder italic text-gray-500 dark:text-gray-400 animate-pulse">Generating response...</p>`;
             messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
        } else {
             console.error("Could not find bot content area with ID:", botMessageId);
             showLoading(); // Fallback to global indicator
        }

        // --- Start EventSource connection ---
        const encodedMessage = encodeURIComponent(messageToSend);
        const streamUrl = `/chat?message=${encodedMessage}&use_reasoning=${useReasoning}`;
        console.log("Connecting to EventSource:", streamUrl);

        eventSource = new EventSource(streamUrl);

        let accumulatedAnswerContent = ''; 
        let sourcesData = [];
        let modelUsed = '';
        let firstChunkReceived = false;
        let thinkingContent = null; 
        let finalAnswerContent = ''; 


        // --- Event Listener for messages (data chunks) ---
        eventSource.onmessage = function(event) {
             // ... (clear placeholder logic) ...
             if (!firstChunkReceived && botContentArea) { 
                botContentArea.innerHTML = ''; // Clear placeholder
                firstChunkReceived = true;
                hideLoading(); // Hide global indicator if it was shown as fallback
              }

            try {
                const data = JSON.parse(event.data);

                if (data.error) { 
                    console.error("SSE Error:", data.error);
                    if(botContentArea) { botContentArea.innerHTML = `<p class="text-red-500">Error: ${escapeHtml(data.error)}</p>`; }
                    else { addMessageToChat("system", `Error: ${data.error}`); }
                    closeEventSource();
                    return;
                 }

                if (data.chunk) {
                    accumulatedAnswerContent += data.chunk;

                    // === START DEBUG LOGGING ===
                    console.log("--- Chunk Received ---");
                    console.log("Chunk:", data.chunk);
                    console.log("Accumulated Raw:", JSON.stringify(accumulatedAnswerContent)); // Show raw with newlines
                    // === END DEBUG LOGGING ===

                    // --- Re-parse and Re-render on each chunk ---
                    if (botContentArea) {
                         thinkingContent = null;
                         finalAnswerContent = accumulatedAnswerContent;

                         const thinkStartTag = "<think>";
                         const thinkEndTag = "</think>";
                         const startIdx = finalAnswerContent.toLowerCase().indexOf(thinkStartTag); // Case-insensitive search
                         const endIdx = finalAnswerContent.toLowerCase().indexOf(thinkEndTag);

                         // === START DEBUG LOGGING (Optional) ===
                         console.log(`Indices - Start: ${startIdx}, End: ${endIdx}`);
                         // === END DEBUG LOGGING ===

                         if (startIdx !== -1) {
                              if (endIdx !== -1 && endIdx > startIdx) {
                                  // Both tags found in correct order
                                  thinkingContent = finalAnswerContent.substring(startIdx + thinkStartTag.length, endIdx).trim();
                                  // Answer is everything *after* the end tag
                                  finalAnswerContent = finalAnswerContent.substring(endIdx + thinkEndTag.length).trim();
                                  // === START DEBUG LOGGING (Optional) ===
                                   console.log("Parsed Thinking:", JSON.stringify(thinkingContent));
                                   console.log("Parsed Answer:", JSON.stringify(finalAnswerContent));
                                  // === END DEBUG LOGGING ===
                              } else {
                                  // Start tag found, but no end tag yet (or it's before start)
                                  // Assume everything after start tag is thinking for now
                                  thinkingContent = finalAnswerContent.substring(startIdx + thinkStartTag.length).trim();
                                  finalAnswerContent = ""; // No final answer part yet
                                  // === START DEBUG LOGGING (Optional) ===
                                   console.log("Parsed Thinking (incomplete):", JSON.stringify(thinkingContent));
                                  // === END DEBUG LOGGING ===
                              }
                         } else {
                            // No <think> start tag found, treat all as answer
                            // Clean up potential </think> tag if it somehow appears alone
                            finalAnswerContent = finalAnswerContent.replace(/<\/think>/gi, '').trim();
                            thinkingContent = null;
                             // === START DEBUG LOGGING (Optional) ===
                             console.log("No valid <think> tags found, treating all as answer.");
                             // === END DEBUG LOGGING ===
                         }
                         // --- ** END OF NEW PARSING LOGIC ** ---


                         // --- *** RENDER MARKDOWN AND MATH *** ---
                        let thinkingHtml = '';
                        if (thinkingContent) {
                            // Render thinking as plain text for now, or optionally markdown+math too
                             thinkingHtml = `<div class="thinking-block mb-2 pb-2 border-b border-gray-200 dark:border-gray-600"><span class="text-xs font-semibold text-gray-500 dark:text-gray-400 block mb-1">Thinking Process:</span><p class="whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-300">${formatBotMessage(thinkingContent)}</p></div>`; // Keep thinking as plain text
                        }
                        // Render final answer using markdown-it
                        const finalAnswerHtml = md.render(finalAnswerContent || ''); // Render markdown

                        // Set combined HTML
                        botContentArea.innerHTML = `${thinkingHtml}<div class="final-answer">${finalAnswerHtml}</div>`; // Wrap final answer
                        const finalAnswerElement = botContentArea.querySelector('.final-answer');
                        if (finalAnswerElement) {
                            console.log("Element to typeset:", finalAnswerElement); // Log the element
                            console.log("Content BEFORE typesetting:", finalAnswerElement.innerHTML.substring(0, 100) + "..."); // Log content

                            if (window.MathJax && window.MathJax.typesetPromise) {
                                console.log("Calling MathJax.typesetPromise..."); // Log before call
                                window.MathJax.typesetPromise([finalAnswerElement])
                                    .then(() => {
                                        console.log("MathJax typesetting finished."); // Log on success
                                        // Optional: Log content AFTER typesetting to compare
                                        // console.log("Content AFTER typesetting:", finalAnswerElement.innerHTML.substring(0, 100) + "...");
                                        messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'auto' });
                                    })
                                    .catch((err) => console.error('MathJax typesetting failed:', err)); // Log errors
                            } else {
                                console.warn("MathJax or typesetPromise not ready yet.");
                                messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
                            }
                        } else {
                            console.error("Could not find .final-answer element!");
                        }

                        // Don't scroll here anymore, scrolling happens after typesetting
                        // messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
                    }
                }
            } catch (e) {
                console.error("Error parsing SSE data:", e, "Raw data:", event.data);
                 if(botContentArea) botContentArea.innerHTML += `<p class="text-red-500 text-xs">[Error processing stream data]</p>`;
            }
        };

        // --- Event Listener for custom 'sources' event ---
        eventSource.addEventListener('sources', function(event) {
             try {
                 sourcesData = JSON.parse(event.data);
                 console.log("Received sources:", sourcesData);
                 const botMessageBubble = document.getElementById(botMessageId)?.closest('.rounded-lg');
                 if (botMessageBubble && sourcesData.length > 0) {
                      let sourcesHtml = '<div class="sources mt-3 pt-3 border-t border-gray-200 dark:border-dark-600"><strong class="text-xs font-semibold text-gray-600 dark:text-gray-400 block mb-1">Sources:</strong><ul class="list-disc pl-5 space-y-1">';
                      sourcesData.forEach(source => { const d = source.filename || source.url?.split('/').pop() || '?'; const u = source.url && source.url.startsWith('http') ? source.url : '#'; sourcesHtml += `<li class="text-xs"><a href="${escapeHtml(u)}" target="_blank" rel="noopener noreferrer" class="text-primary-600 dark:text-primary-400 hover:underline break-all" title="${escapeHtml(source.url || '')}">${escapeHtml(d)}</a></li>`; });
                      sourcesHtml += '</ul></div>';
                      // Remove previous sources div if it exists, then append new one
                      botMessageBubble.querySelector('.sources')?.remove();
                      botMessageBubble.insertAdjacentHTML('beforeend', sourcesHtml);
                      messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
                 }
             } catch (e) { console.error("Error parsing sources data:", e); }
        });

        // --- Event Listener for stream end ---
        eventSource.addEventListener('end', function(event) {
            console.log("Stream ended by server.");
             try {
                 const endData = JSON.parse(event.data);
                 modelUsed = endData.model_used || '';
                 console.log("Model used:", modelUsed);
                 // Update timestamp if needed (already set initially)
                 const timestampEl = document.getElementById(botMessageId)?.closest('.rounded-lg')?.querySelector('.message-timestamp');
                 if (timestampEl) timestampEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

             } catch(e) { console.error("Could not parse end event data:", e); }
            closeEventSource();
            hideLoading(); // Ensure global loading is hidden if used as fallback
        });

        // --- Event Listener for errors ---
        eventSource.onerror = function(error) {
            console.error("EventSource failed:", error);
            addMessageToChat("system", "Connection lost or stream error.");
             const botContentArea = document.getElementById(botMessageId);
             if (botContentArea && !firstChunkReceived) { botContentArea.innerHTML = `<p class="text-red-500">Connection error.</p>`; }
             else if (botContentArea) { botContentArea.innerHTML += `<p class="text-red-500 text-xs">[Stream Error]</p>`; }
            closeEventSource();
            hideLoading(); // Ensure global loading is hidden
        };
    }

    // Helper function to close EventSource
    function closeEventSource() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
            console.log("EventSource connection closed.");
        }
    }

    // --- Add Message to Chat UI (Handles thinking/answer split, sources) ---
    function addMessageToChat(sender, message, modeOrModel = null, sources = [], thinking = null, messageId = null) {
        if (!messagesContainer) return;
        const now = new Date(); const timeString = now.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit'});
        const messageWrapper = document.createElement('div'); messageWrapper.className = 'chat-message'; const messageDiv = document.createElement('div');

        if (sender === 'user') {
            messageDiv.className = 'flex items-start justify-end';
            messageDiv.innerHTML = `<div class="bg-primary-600 text-white rounded-lg p-3 sm:p-4 inline-block max-w-xs sm:max-w-sm md:max-w-md lg:max-w-lg xl:max-w-xl ml-auto"><p class="whitespace-pre-wrap">${escapeHtml(message)}</p><p class="text-xs text-primary-200 mt-2 text-right">${timeString}</p></div>`;
        } else if (sender === 'bot-init') { // Creates the initial bubble structure
             messageDiv.className = 'flex items-start';
             const isReasoning = currentChatMode === 'reasoning';
             const modelBaseName = isReasoning ? REASONING_LLM_MODEL.split(':')[0] : DEFAULT_LLM_MODEL.split(':')[0];
             const iconClass = isReasoning ? 'fas fa-brain text-purple-600 dark:text-purple-400' : 'fas fa-lock text-primary-600 dark:text-primary-400';
             const iconBgClass = isReasoning ? 'bg-purple-100 dark:bg-purple-900/30' : 'bg-primary-100 dark:bg-dark-700';
             const bubbleClass = isReasoning ? 'bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800' : 'bg-gray-100 dark:bg-dark-700';
             const reasoningHeader = isReasoning ? `<div class="flex items-center mb-2"><span class="bg-purple-600 text-white text-xs px-2 py-1 rounded-full mr-2">Reasoning</span><span class="text-xs text-purple-600 dark:text-purple-400">${modelBaseName} Analysis</span></div>` : '';
             // Note: No sources or main content here initially
             messageDiv.innerHTML = `
                 <div class="${iconBgClass} p-3 rounded-full mr-3 flex-shrink-0 flex items-center justify-center self-start mt-1"><i class="${iconClass}"></i></div>
                 <div class="flex-1 max-w-xs sm:max-w-sm md:max-w-md lg:max-w-lg xl:max-w-xl">
                     <div class="${bubbleClass} rounded-lg p-3 sm:p-4 inline-block">
                         ${reasoningHeader}
                         
                         <div id="${messageId}">
                             {/* Content will be streamed here */}
                         </div>
                         
                         <p class="message-timestamp text-xs text-gray-500 dark:text-gray-400 mt-2">${timeString}</p>
                     </div>
                 </div>`;
        } else if (sender === 'system') {
            messageDiv.className = 'flex items-center justify-center system-message';
            messageDiv.innerHTML = `<div class="bubble text-center text-xs px-3 py-2 rounded-md"><i class="fas fa-exclamation-triangle mr-1"></i> ${escapeHtml(message)}</div>`;
        }

        messageWrapper.appendChild(messageDiv);
        messagesContainer.appendChild(messageWrapper);
        // Scroll only for user/system, initial bubble scroll handled after placeholder added
        if(sender !== 'bot-init') { messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' }); }
    }
    // --- END of Add Message ---


    // --- NEW: Functions for fetching and rendering reference files ---

    async function fetchAndDisplayReferenceFiles() {
        console.log("Fetching reference files from backend...");
        // Show some loading state in sidebar if desired
        if (sidebarDocsContainer) sidebarDocsContainer.innerHTML = '<p class="text-xs text-gray-400 px-3 animate-pulse">Loading files...</p>';

        try {
            const response = await fetch("/list_files"); // Call the new backend route
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();

            if (data.error) {
                 throw new Error(`Backend error: ${data.error}`);
            }

            allFetchedFiles = data.files || []; // Store the full list globally
            console.log(`Fetched ${allFetchedFiles.length} reference files.`);

            // Render the initial limited list in the sidebar
            renderSidebarFiles(allFetchedFiles);

            // Pre-render modal content too, but keep modal hidden initially
            // This avoids a delay when the user clicks "View All"
            renderModalFiles(allFetchedFiles);


        } catch (error) {
            console.error("Error fetching or processing reference files:", error);
             if (sidebarDocsContainer) sidebarDocsContainer.innerHTML = `<p class="text-xs text-red-500 px-3">Error loading files: ${error.message}</p>`;
             // Also show error in modal maybe?
              if (modalDocsContainer) modalDocsContainer.innerHTML = `<p class="text-center col-span-full text-red-500 py-6">Error loading documents: ${error.message}</p>`;
               // Hide the "View All" button on error
              if(viewAllDocsBtn) viewAllDocsBtn.style.display = 'none';
        }
    }

    function renderSidebarFiles(files) {
        if (!sidebarDocsContainer) return;
        sidebarDocsContainer.innerHTML = ''; // Clear placeholders/loading
        const filesToShow = files.slice(0, 2); // Show only the first 2 files

        if (filesToShow.length === 0) {
             sidebarDocsContainer.innerHTML = '<p class="text-xs text-gray-500 dark:text-gray-400 px-3">No reference files found.</p>';
        } else {
            filesToShow.forEach(file => {
                // Use 'false' for isModal flag to get sidebar style
                const fileHtml = createFileElementHtml(file, false);
                sidebarDocsContainer.insertAdjacentHTML('beforeend', fileHtml);
            });
        }

        // Show "View All" button only if there are more files than shown
        if (viewAllDocsBtn) {
           viewAllDocsBtn.style.display = files.length > filesToShow.length ? 'flex' : 'none';
       }
    }
    
    // --- NEW: File Upload Handling ---

    function handleFileUpload(event) {
        if (event.target.files.length === 0) {
            console.log("No file selected.");
            return; // No file chosen
        }

        const file = event.target.files[0];
        const allowedTypes = ['application/pdf', 'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'];
        const maxFileSize = 25 * 1024 * 1024; // Example: 25 MB limit

        // Basic Validation
        if (!allowedTypes.includes(file.type)) {
            showNotification(`Invalid file type. Please upload PDF or PPTX/PPT files.`);
            event.target.value = null; // Reset input
            return;
        }
        if (file.size > maxFileSize) {
             showNotification(`File size exceeds limit (${(maxFileSize / (1024*1024)).toFixed(0)} MB).`);
             event.target.value = null; // Reset input
             return;
        }

        console.log(`File selected: ${file.name}, Type: ${file.type}, Size: ${file.size}`);

        // Prepare data for upload
        const formData = new FormData();
        formData.append('file', file); // Key 'file' must match backend request.files lookup

        // Call the upload function
        uploadFileToS3(formData);

        // Reset the input value so the 'change' event fires even if the same file is selected again
        event.target.value = null;
    }

    async function uploadFileToS3(formData) {
        console.log("Attempting to upload file...");
        showLoading(); // Show general loading indicator

        try {
            const response = await fetch("/upload_file", {
                method: "POST",
                body: formData,
                // NOTE: Do NOT set Content-Type header manually for FormData
                // The browser will set it correctly with the boundary
            });

            hideLoading(); // Hide indicator after response

            if (!response.ok) {
                let errorMsg = `Upload failed: ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    errorMsg = `Upload failed: ${errorData?.error || response.statusText}`;
                } catch (e) { /* Ignore if response not JSON */ }
                console.error("File upload error:", errorMsg);
                showNotification(errorMsg); // Show error notification
                return; // Stop further processing
            }

            // --- Success ---
            const data = await response.json();
            console.log("Upload successful:", data);
            showNotification(data.message || `File '${data.filename || 'file'}' uploaded successfully!`);

            // *** Refresh the file list to show the newly uploaded file ***
            fetchAndDisplayReferenceFiles();

        } catch (error) {
            hideLoading(); // Hide indicator on network error
            console.error("Network error during file upload:", error);
            showNotification("Network error during upload. Please try again.");
        }
    }
    function renderModalFiles(files) {
         if (!modalDocsContainer) return;
         modalDocsContainer.innerHTML = ''; // Clear previous content/loading

         if (files.length === 0) {
              modalDocsContainer.innerHTML = '<p class="text-center col-span-full text-gray-500 dark:text-gray-400 py-6">No reference files found in the S3 bucket.</p>';
         } else {
             files.forEach(file => {
                 // Use 'true' for isModal flag to get modal card style
                 const fileHtml = createFileElementHtml(file, true);
                 modalDocsContainer.insertAdjacentHTML('beforeend', fileHtml);
             });
         }

         // Update modal pagination display
         if (modalPaginationInfo) {
             modalPaginationInfo.textContent = `Showing ${files.length} of ${files.length} documents`;
         }
    }

    // Helper function to create HTML for a single file item
    function createFileElementHtml(file, isModal = false) {
        const filename = escapeHtml(file.filename || 'Unknown File');
        // Format size nicely
        let sizeFormatted = 'N/A';
        if (typeof file.size === 'number') {
             if (file.size < 1024) sizeFormatted = `${file.size} B`;
             else if (file.size < 1024 * 1024) sizeFormatted = `${(file.size / 1024).toFixed(1)} KB`;
             else sizeFormatted = `${(file.size / (1024 * 1024)).toFixed(1)} MB`;
        }
        const url = escapeHtml(file.public_url || '#');
        const fileExtension = (filename.split('.').pop() || '').toLowerCase();

        // Determine icon styles based on extension
        let iconClass = 'fas fa-file-alt';
        let iconColorClass = 'text-gray-600 dark:text-gray-400';
        let iconBgClass = 'bg-gray-100 dark:bg-gray-900/30';
        if (fileExtension === 'pdf') { iconClass = 'fas fa-file-pdf'; iconColorClass = 'text-red-600 dark:text-red-400'; iconBgClass = 'bg-red-100 dark:bg-red-900/30'; }
        else if (['ppt', 'pptx'].includes(fileExtension)) { iconClass = 'fas fa-file-powerpoint'; iconColorClass = 'text-blue-600 dark:text-blue-400'; iconBgClass = 'bg-blue-100 dark:bg-blue-900/30'; }
        else if (['txt', 'md'].includes(fileExtension)) { iconClass = 'fas fa-file-alt'; iconColorClass = 'text-green-600 dark:text-green-400'; iconBgClass = 'bg-green-100 dark:bg-green-900/30'; }
        else if (['doc', 'docx'].includes(fileExtension)) { iconClass = 'fas fa-file-word'; iconColorClass = 'text-blue-700 dark:text-blue-500'; iconBgClass = 'bg-blue-100 dark:bg-blue-900/30'; }
        else if (['xls', 'xlsx'].includes(fileExtension)) { iconClass = 'fas fa-file-excel'; iconColorClass = 'text-green-700 dark:text-green-500'; iconBgClass = 'bg-green-100 dark:bg-green-900/30'; }


         // Define classes based on context (modal vs sidebar)
         const containerClass = isModal
            ? 'document-card p-4 bg-gray-50 dark:bg-dark-700 rounded-lg border border-gray-200 dark:border-dark-600 hover:shadow-md cursor-pointer transition-all'
            : 'document-item p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-700 cursor-pointer flex items-center transition-colors';
         const iconContainerClass = isModal
             ? `${iconBgClass} p-3 rounded-lg mr-4 flex items-center justify-center self-start`
             : `${iconBgClass} p-2 rounded-lg mr-3 flex items-center justify-center flex-shrink-0`; // Added flex-shrink-0
         const iconSizeClass = isModal ? 'text-2xl' : 'text-lg';
         const contentContainerClass = isModal ? 'flex-1 min-w-0' : 'min-w-0'; // Allow text truncation

         // Action buttons (only in modal)
         const actionsHtml = isModal ? `
             <div class="flex justify-between items-center mt-3">
                 <span class="text-xs text-gray-500 dark:text-gray-400">${fileExtension.toUpperCase()} • ${sizeFormatted}</span>
                 <a href="${url}" target="_blank" rel="noopener noreferrer" class="text-primary-600 dark:text-primary-400 hover:underline text-sm font-medium transition-colors">
                     Open <i class="fas fa-external-link-alt text-xs ml-1"></i>
                 </a>
             </div>
         ` : '';

         // Description/Key for modal view
         const descriptionHtml = isModal ? `<p class="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate" title="${escapeHtml(file.key || '')}">Path: ${escapeHtml(file.key || 'N/A')}</p>` : '';

        return `
            <div class="${containerClass}" title="${filename} (${sizeFormatted})">
                <div class="flex items-start">
                    <div class="${iconContainerClass}">
                        <i class="${iconClass} ${iconColorClass} ${iconSizeClass}"></i>
                    </div>
                    <div class="${contentContainerClass}">
                        <h3 class="font-medium text-sm truncate" title="${filename}">${filename}</h3>
                        ${isModal ? descriptionHtml : `<p class="text-xs text-gray-500 dark:text-gray-400">${sizeFormatted}</p>`}
                        ${actionsHtml}
                    </div>
                </div>
            </div>
        `;
    }


    // --- Other existing helper functions ---
     function updateCurrentSessionTimestamp() { if(currentSessionTimestamp) currentSessionTimestamp.textContent = `Started: ${currentSessionStartTime.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}`; }
     function checkHistoryPlaceholder() { if(sessionListContainer?.children.length === 0) sessionListContainer.innerHTML='<p class="text-xs ... no-history-message">No previous sessions yet.</p>'; else sessionListContainer.querySelector('.no-history-message')?.remove();} 
     function toggleDarkMode() { if(isDarkMode)disableDarkMode();else enableDarkMode(); }
     function enableDarkMode() { document.documentElement.classList.add('dark'); if(darkModeToggle) darkModeToggle.innerHTML='<i class="fas fa-sun"></i>'; isDarkMode=true; localStorage.setItem('darkMode','true'); }
     function disableDarkMode() { document.documentElement.classList.remove('dark'); if(darkModeToggle) darkModeToggle.innerHTML='<i class="fas fa-moon"></i>'; isDarkMode=false; localStorage.setItem('darkMode','false'); }
     function toggleModeDropdown() { modeDropdown?.classList.toggle('hidden'); modeDropdownIcon?.classList.toggle('rotate-180'); }
     function setChatMode(mode) { currentChatMode=mode; console.log("Chat mode set to:", currentChatMode); updateModeButtonDisplay(); }
     function updateModeButtonDisplay() { if(currentMode){ if(currentChatMode==='normal')currentMode.textContent='Normal Chat'; else if(currentChatMode==='reasoning')currentMode.textContent='Reasoning Mode'; else if(currentChatMode==='search')currentMode.textContent='Online Search'; } if(reasoningBtn){ if(currentChatMode==='reasoning'){ reasoningBtn.classList.remove('bg-purple-600','hover:bg-purple-700'); reasoningBtn.classList.add('bg-purple-800','hover:bg-purple-900'); } else { reasoningBtn.classList.remove('bg-purple-800','hover:bg-purple-900'); reasoningBtn.classList.add('bg-purple-600','hover:bg-purple-700'); } } }
     function toggleQuickTerms() { quickTerms?.classList.toggle('hidden'); quickTermsToggle?.classList.toggle('text-primary-600'); quickTermsToggle?.classList.toggle('dark:text-primary-400'); }
     function updateCharCount() { if(!messageInput||!charCount)return; const count=messageInput.value.length; charCount.textContent=`${count}/1000`; if(count>900){ charCount.classList.add('text-red-500'); charCount.classList.remove('text-gray-500','dark:text-gray-400'); }else{ charCount.classList.remove('text-red-500'); charCount.classList.add('text-gray-500','dark:text-gray-400'); } }
     function addThinkingMessage() { removeThinkingMessage(); const t=document.createElement('div'); t.className='chat-message thinking-bubble'; t.id='thinking-indicator-message'; t.innerHTML=`<div class="flex items-start"><div class="bg-primary-100 dark:bg-dark-700 p-3 rounded-full mr-3 flex-shrink-0 flex items-center justify-center self-start mt-1"><i class="fas fa-spinner fa-spin text-primary-600 dark:text-primary-400"></i></div><div class="flex-1 max-w-xs sm:max-w-sm md:max-w-md lg:max-w-lg xl:max-w-xl"><div class="bubble rounded-lg p-3 sm:p-4 inline-block"><p class="text italic animate-pulse">Thinking...</p></div></div></div>`; messagesContainer?.appendChild(t); messagesContainer?.scrollTo({top:messagesContainer.scrollHeight, behavior:'smooth'}); }
     function removeThinkingMessage() { document.getElementById('thinking-indicator-message')?.remove(); }
     function escapeHtml(unsafe) { if(typeof unsafe !=='string')return unsafe; return unsafe.replace(/&/g,"&").replace(/</g,"<").replace(/>/g,">").replace(/'/g,"'"); }
     function formatBotMessage(message) { let f=escapeHtml(message); return f; } // f=f.replace(/\n/g,'<br>'); return f; }
     function performSearch() {  }
     function showLoading() { if(loadingIndicator){ loadingIndicator.classList.remove('hidden'); setTimeout(()=>{loadingIndicator.classList.remove('opacity-0');},10); } }
     function hideLoading() { if(loadingIndicator){ loadingIndicator.classList.add('opacity-0'); setTimeout(()=>{loadingIndicator.classList.add('hidden');},300); } }
     function showNotification(message) { if(notification& notificationMessage){ notificationMessage.textContent=message; notification.classList.remove('hidden'); setTimeout(()=>{notification.classList.remove('translate-y-4','opacity-0'); notification.classList.add('translate-y-0','opacity-100');},10); setTimeout(()=>{notification.classList.add('translate-y-4','opacity-0'); setTimeout(()=>{notification.classList.add('hidden');},300);},3000); } }
     function showExportNotification() { showLoading(); setTimeout(()=>{hideLoading(); showNotification('Session export simulated!');},1000); }
     async function startNewBackendSession() { console.log("Starting new session..."); showLoading(); try { const r=await fetch("/new_session",{method:"POST"}); if(!r.ok){ const e=await r.json(); console.error("Error clearing session:",r.statusText,e); addMessageToChat("system",`Error: ${e?.message||r.statusText}`); }else{ const d=await r.json(); console.log("Backend:",d.message); if(messagesContainer){ const m=messagesContainer.querySelectorAll('.chat-message'); const s=m.length>0&&m[0].innerText.includes("Hello! I'm your CryptoSec assistant")?1:0; for(let i=m.length-1;i>=s;i--){m[i].remove();} } showNotification('New session started!'); } }catch(error){ console.error("Network error:",error); addMessageToChat("system","Network error starting session."); }finally{ hideLoading(); } }

    const DEFAULT_LLM_MODEL = "qwen2.5:7b";
    const REASONING_LLM_MODEL = "deepseek-r1:7b";
    
    // Initialize the app
    init();
});

