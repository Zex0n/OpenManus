let currentEventSource = null;
let currentTaskId = null;

let exampleApiKey = '';

// Use example configuration to fill in the form
function fillConfigForm(exampleConfig) {
    if (exampleConfig.llm) {
        const llm = exampleConfig.llm;

        setInputValue('llm-model', llm.model);
        setInputValue('llm-base-url', llm.base_url);
        setInputValue('llm-api-key', llm.api_key);

        exampleApiKey = llm.api_key || '';

        setInputValue('llm-max-tokens', llm.max_tokens);
        setInputValue('llm-temperature', llm.temperature);
    }

    if (exampleConfig.server) {
        setInputValue('server-host', exampleConfig.server.host);
        setInputValue('server-port', exampleConfig.server.port);
    }
}

function setInputValue(id, value) {
    const input = document.getElementById(id);
    if (input && value !== undefined) {
        input.value = value;
    }
}

function saveConfig() {
    const configData = collectFormData();

    const requiredFields = [
        { id: 'llm-model', name: 'Model Name' },
        { id: 'llm-base-url', name: 'API Base URL' },
        { id: 'llm-api-key', name: 'API Key' },
        { id: 'server-host', name: 'Server Host' },
        { id: 'server-port', name: 'Server Port' }
    ];

    let missingFields = [];
    requiredFields.forEach(field => {
        if (!document.getElementById(field.id).value.trim()) {
            missingFields.push(field.name);
        }
    });

    if (missingFields.length > 0) {
        document.getElementById('config-error').textContent =
            `Please fill in the necessary configuration information: ${missingFields.join(', ')}`;
        return;
    }

    // Check if the API key is the same as the example configuration
    const apiKey = document.getElementById('llm-api-key').value.trim();
    if (apiKey === exampleApiKey && exampleApiKey.includes('sk-')) {
        document.getElementById('config-error').textContent =
            `Please enter your own API key`;
        document.getElementById('llm-api-key').parentElement.classList.add('error');
        return;
    } else {
        document.getElementById('llm-api-key').parentElement.classList.remove('error');
    }

    fetch('/config/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(configData)
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                document.getElementById('config-modal').classList.remove('active');
                document.getElementById('input-container').classList.remove('disabled');
                alert('Configuration saved successfully! The application will use the new configuration on next startup.');
                window.location.reload();
            } else {
                document.getElementById('config-error').textContent =
                    `Save failed: ${data.message}`;
            }
        })
        .catch(error => {
            document.getElementById('config-error').textContent =
                `Request error: ${error.message}`;
        });
}

// Collect form data
function collectFormData() {
    const configData = {
        llm: {
            model: document.getElementById('llm-model').value,
            base_url: document.getElementById('llm-base-url').value,
            api_key: document.getElementById('llm-api-key').value
        },
        server: {
            host: document.getElementById('server-host').value,
            port: parseInt(document.getElementById('server-port').value || '5172')
        }
    };

    const maxTokens = document.getElementById('llm-max-tokens').value;
    if (maxTokens) {
        configData.llm.max_tokens = parseInt(maxTokens);
    }

    const temperature = document.getElementById('llm-temperature').value;
    if (temperature) {
        configData.llm.temperature = parseFloat(temperature);
    }

    return configData;
}

function createTask() {
    const promptInput = document.getElementById('prompt-input');
    const prompt = promptInput.value.trim();

    if (!prompt) {
        alert("Please enter a valid prompt");
        promptInput.focus();
        return;
    }

    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }

    const container = document.getElementById('task-container');
    container.innerHTML = '<div class="loading">Initializing task...</div>';
    document.getElementById('input-container').classList.add('bottom');

    // Show cancel button
    showCancelButton();

    fetch('/tasks', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt })
    })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || 'Request failed') });
            }
            return response.json();
        })
        .then(data => {
            if (!data.task_id) {
                throw new Error('Invalid task ID');
            }
            currentTaskId = data.task_id;
            setupSSE(data.task_id);
            loadHistory();
            promptInput.value = '';
        })
        .catch(error => {
            container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
            hideCancelButton();
            console.error('Failed to create task:', error);
        });
}

function setupSSE(taskId) {
    let retryCount = 0;
    const maxRetries = 3;
    const retryDelay = 2000;
    let lastResultContent = '';

    const container = document.getElementById('task-container');

    function connect() {
        const eventSource = new EventSource(`/tasks/${taskId}/events`);
        currentEventSource = eventSource;

        let heartbeatTimer = setInterval(() => {
            container.innerHTML += '<div class="ping">·</div>';
        }, 5000);

        // Initial polling
        fetch(`/tasks/${taskId}`)
            .then(response => response.json())
            .then(task => {
                updateTaskStatus(task);
            })
            .catch(error => {
                console.error('Initial status fetch failed:', error);
            });

        const handleEvent = (event, type) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();
                container.classList.add('active');

                const stepContainer = ensureStepContainer(container);
                const { formattedContent, timestamp } = formatStepContent(data, type);
                const step = createStepElement(type, formattedContent, timestamp);

                stepContainer.appendChild(step);
                autoScroll(stepContainer);

                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('Status update failed:', error);
                    });
            } catch (e) {
                console.error(`Error handling ${type} event:`, e);
            }
        };

        const eventTypes = ['think', 'tool', 'act', 'log', 'run', 'message'];
        eventTypes.forEach(type => {
            eventSource.addEventListener(type, (event) => handleEvent(event, type));
        });

        // Special handler for ask_human events
        eventSource.addEventListener('ask_human', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.querySelector('.loading')?.remove();
                container.classList.add('active');

                const stepContainer = ensureStepContainer(container);
                const humanRequestElement = createHumanRequestElement(data, taskId);
                stepContainer.appendChild(humanRequestElement);
                autoScroll(stepContainer);
            } catch (e) {
                console.error('Error handling ask_human event:', e);
            }
        });

        eventSource.addEventListener('complete', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                lastResultContent = data.result || '';

                container.innerHTML += `
                    <div class="complete">
                        <div>✅ Task completed</div>
                        <pre>${lastResultContent}</pre>
                    </div>
                `;

                // Hide cancel button
                hideCancelButton();

                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('Final status update failed:', error);
                    });

                eventSource.close();
                currentEventSource = null;
                currentTaskId = null;
            } catch (e) {
                console.error('Error handling complete event:', e);
            }
        });

        eventSource.addEventListener('error', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.innerHTML += `
                    <div class="error">
                        ❌ Error: ${data.message}
                    </div>
                `;

                // Hide cancel button
                hideCancelButton();

                eventSource.close();
                currentEventSource = null;
                currentTaskId = null;
            } catch (e) {
                console.error('Error handling failed:', e);
            }
        });

        eventSource.addEventListener('cancelled', (event) => {
            clearInterval(heartbeatTimer);
            try {
                const data = JSON.parse(event.data);
                container.innerHTML += `
                    <div class="cancelled">
                        🚫 Task was cancelled by user
                    </div>
                `;

                // Hide cancel button
                hideCancelButton();

                fetch(`/tasks/${taskId}`)
                    .then(response => response.json())
                    .then(task => {
                        updateTaskStatus(task);
                    })
                    .catch(error => {
                        console.error('Final status update failed:', error);
                    });

                eventSource.close();
                currentEventSource = null;
                currentTaskId = null;
            } catch (e) {
                console.error('Error handling cancelled event:', e);
            }
        });

        eventSource.onerror = (err) => {
            if (eventSource.readyState === EventSource.CLOSED) return;

            console.error('SSE connection error:', err);
            clearInterval(heartbeatTimer);
            eventSource.close();

            fetch(`/tasks/${taskId}`)
                .then(response => response.json())
                .then(task => {
                    if (task.status === 'completed' || task.status === 'failed') {
                        updateTaskStatus(task);
                        if (task.status === 'completed') {
                            container.innerHTML += `
                                <div class="complete">
                                    <div>✅ Task completed</div>
                                </div>
                            `;
                        } else {
                            container.innerHTML += `
                                <div class="error">
                                    ❌ Error: ${task.error || 'Task failed'}
                                </div>
                            `;
                        }
                    } else if (retryCount < maxRetries) {
                        retryCount++;
                        container.innerHTML += `
                            <div class="warning">
                                ⚠ Connection lost, retrying in ${retryDelay / 1000} seconds (${retryCount}/${maxRetries})...
                            </div>
                        `;
                        setTimeout(connect, retryDelay);
                    } else {
                        container.innerHTML += `
                            <div class="error">
                                ⚠ Connection lost, please try refreshing the page
                            </div>
                        `;
                    }
                })
                .catch(error => {
                    console.error('Task status check failed:', error);
                    if (retryCount < maxRetries) {
                        retryCount++;
                        setTimeout(connect, retryDelay);
                    }
                });
        };
    }

    connect();
}

function loadHistory() {
    console.log('loadHistory called');
    fetch('/tasks')
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`request failure: ${response.status} - ${text.substring(0, 100)}`);
                });
            }
            return response.json();
        })
        .then(tasks => {
            const listContainer = document.getElementById('task-list');
            listContainer.innerHTML = tasks.map(task => `
            <div class="task-card" data-task-id="${task.id}">
                <div class="task-prompt">${task.prompt}</div>
                <div class="task-meta">
                    ${new Date(task.created_at).toLocaleString()} -
                    <span class="status status-${task.status ? task.status.toLowerCase() : 'unknown'}">
                        ${task.status || 'Unknown state'}
                    </span>
                </div>
                <div class="task-result-preview">
                    ${task.result ? `<pre>${task.result.substring(0, 120)}${task.result.length > 120 ? '...' : ''}</pre>` : '<button class="show-details-btn">Details</button>'}
                </div>
            </div>
        `).join('');
            // Add click handler to task card
            Array.from(listContainer.getElementsByClassName('task-card')).forEach(card => {
                card.onclick = function () {
                    const taskId = this.getAttribute('data-task-id');
                    showTaskDetails(taskId);
                };
            });
        })
        .catch(error => {
            console.error('Failed to load history records:', error);
            const listContainer = document.getElementById('task-list');
            listContainer.innerHTML = `<div class="error">Load Fail: ${error.message}</div>`;
        });
}

function showTaskDetails(taskId) {
    fetch(`/tasks/${taskId}`)
        .then(response => {
            if (!response.ok) throw new Error('Failed to load task');
            return response.json();
        })
        .then(task => {
            const container = document.getElementById('task-container');
            let html = `<div class="task-details">
                <h2>Task</h2>
                <div><b>Prompt:</b> <pre>${task.prompt}</pre></div>
                <div><b>Status:</b> ${task.status}</div>
                <div><b>Created:</b> ${new Date(task.created_at).toLocaleString()}</div>
                <h3>Result</h3>
                <pre>${task.result || 'No result'}</pre>
                <h3>Steps</h3>
                <div class="task-steps">${(task.steps || []).map((step, idx) => `
                    <div class="task-step"><b>${step.type || 'step'} #${step.step ?? idx}:</b><pre>${step.result}</pre></div>
                `).join('')}</div>
            </div>`;
            container.innerHTML = html;
        })
        .catch(error => {
            const container = document.getElementById('task-container');
            container.innerHTML = `<div class="error">Error: ${error.message}</div>`;
        });
}


function ensureStepContainer(container) {
    let stepContainer = container.querySelector('.step-container');
    if (!stepContainer) {
        container.innerHTML = '<div class="step-container"></div>';
        stepContainer = container.querySelector('.step-container');
    }
    return stepContainer;
}

function formatStepContent(data, eventType) {
    return {
        formattedContent: data.result,
        timestamp: new Date().toLocaleTimeString()
    };
}

function createStepElement(type, content, timestamp) {
    const step = document.createElement('div');

    // Executing step
    const stepRegex = /Executing step (\d+)\/(\d+)/;
    if (type === 'log' && stepRegex.test(content)) {
        const match = content.match(stepRegex);
        const currentStep = parseInt(match[1]);
        const totalSteps = parseInt(match[2]);

        step.className = 'step-divider';
        step.innerHTML = `
            <div class="step-circle">${currentStep}</div>
            <div class="step-line"></div>
            <div class="step-info">${currentStep}/${totalSteps}</div>
        `;
    } else if (type === 'act') {
        // Check if it contains information about file saving
        const saveRegex = /Content successfully saved to (.+)/;
        const match = content.match(saveRegex);

        step.className = `step-item ${type}`;

        if (match && match[1]) {
            const filePath = match[1].trim();
            const fileName = filePath.split('/').pop();
            const fileExtension = fileName.split('.').pop().toLowerCase();

            // Handling different types of files
            let fileInteractionHtml = '';

            if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp'].includes(fileExtension)) {
                fileInteractionHtml = `
                    <div class="file-interaction image-preview">
                        <img src="${fileName}" alt="${fileName}" class="preview-image" onclick="showFullImage('${fileName}')">
                        <a href="/download?file_path=${fileName}" download="${fileName}" class="download-link">⬇️ Download Image</a>
                    </div>
                `;
            } else if (['mp3', 'wav', 'ogg'].includes(fileExtension)) {
                fileInteractionHtml = `
                    <div class="file-interaction audio-player">
                        <audio controls src="${fileName}"></audio>
                        <a href="/download?file_path=${fileName}" download="${fileName}" class="download-link">⬇️ Download Audio</a>
                    </div>
                `;
            } else if (['html', 'js', 'py'].includes(fileExtension)) {
                fileInteractionHtml = `
                    <div class="file-interaction code-file">
                        <button onclick="simulateRunPython('${fileName}')" class="run-button">▶️ Simulate Run</button>
                        <a href="/download?file_path=${fileName}" download="${fileName}" class="download-link">⬇️ Download File</a>
                    </div>
                `;
            } else {
                fileInteractionHtml = `
                    <div class="file-interaction">
                        <a href="/download?file_path=${fileName}" download="${fileName}" class="download-link">⬇️ Download File: ${fileName}</a>
                    </div>
                `;
            }

            step.innerHTML = `
                <div class="log-line">
                    <span class="log-prefix">${getEventIcon(type)} [${timestamp}] ${getEventLabel(type)}:</span>
                    <pre>${content}</pre>
                    ${fileInteractionHtml}
                </div>
            `;
        } else {
            step.innerHTML = `
                <div class="log-line">
                    <span class="log-prefix">${getEventIcon(type)} [${timestamp}] ${getEventLabel(type)}:</span>
                    <pre>${content}</pre>
                </div>
            `;
        }
    } else {
        step.className = `step-item ${type}`;
        step.innerHTML = `
            <div class="log-line">
                <span class="log-prefix">${getEventIcon(type)} [${timestamp}] ${getEventLabel(type)}:</span>
                <pre>${content}</pre>
            </div>
        `;
    }
    return step;
}

function autoScroll(element) {
    requestAnimationFrame(() => {
        element.scrollTo({
            top: element.scrollHeight,
            behavior: 'smooth'
        });
    });
    setTimeout(() => {
        element.scrollTop = element.scrollHeight;
    }, 100);
}


function getEventIcon(eventType) {
    const icons = {
        'think': '🤔',
        'tool': '🛠️',
        'act': '🚀',
        'result': '🏁',
        'error': '❌',
        'complete': '✅',
        'log': '📝',
        'run': '⚙️',
        'ask_human': '💬'
    };
    return icons[eventType] || 'ℹ️';
}

function getEventLabel(eventType) {
    const labels = {
        'think': 'Thinking',
        'tool': 'Using Tool',
        'act': 'Action',
        'result': 'Result',
        'error': 'Error',
        'complete': 'Complete',
        'log': 'Log',
        'run': 'Running',
        'ask_human': 'Question for User'
    };
    return labels[eventType] || 'Info';
}

function updateTaskStatus(task) {
    const statusBar = document.getElementById('status-bar');
    if (!statusBar) return;

    if (task.status === 'completed') {
        statusBar.innerHTML = `<span class="status-complete">✅ Task completed</span>`;
        hideCancelButton();

        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
    } else if (task.status === 'cancelled') {
        statusBar.innerHTML = `<span class="status-cancelled">🚫 Task cancelled</span>`;
        hideCancelButton();

        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
    } else if (task.status === 'failed') {
        statusBar.innerHTML = `<span class="status-error">❌ Task failed: ${task.error || 'Unknown error'}</span>`;
        hideCancelButton();

        if (currentEventSource) {
            currentEventSource.close();
            currentEventSource = null;
        }
    } else if (task.status === 'running') {
        statusBar.innerHTML = `<span class="status-running">⚙️ Task running: ${task.status}</span>`;
        showCancelButton();
    } else {
        statusBar.innerHTML = `<span class="status-running">⚙️ Task running: ${task.status}</span>`;
    }
}

// Display full screen image
function showFullImage(imageSrc) {
    const modal = document.getElementById('image-modal');
    if (!modal) {
        const modalDiv = document.createElement('div');
        modalDiv.id = 'image-modal';
        modalDiv.className = 'image-modal';
        modalDiv.innerHTML = `
            <span class="close-modal">&times;</span>
            <img src="${imageSrc}" class="modal-content" id="full-image">
        `;
        document.body.appendChild(modalDiv);

        const closeBtn = modalDiv.querySelector('.close-modal');
        closeBtn.addEventListener('click', () => {
            modalDiv.classList.remove('active');
        });

        modalDiv.addEventListener('click', (e) => {
            if (e.target === modalDiv) {
                modalDiv.classList.remove('active');
            }
        });

        setTimeout(() => modalDiv.classList.add('active'), 10);
    } else {
        document.getElementById('full-image').src = imageSrc;
        modal.classList.add('active');
    }
}

// Simulate running Python files
function simulateRunPython(filePath) {
    let modal = document.getElementById('python-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'python-modal';
        modal.className = 'python-modal';
        modal.innerHTML = `
            <div class="python-console">
                <div class="close-modal">&times;</div>
                <div class="python-output">Loading Python file contents...</div>
            </div>
        `;
        document.body.appendChild(modal);

        const closeBtn = modal.querySelector('.close-modal');
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }

    modal.classList.add('active');

    // Load Python file content
    fetch(filePath)
        .then(response => response.text())
        .then(code => {
            const outputDiv = modal.querySelector('.python-output');
            outputDiv.innerHTML = '';

            const codeElement = document.createElement('pre');
            codeElement.textContent = code;
            codeElement.style.marginBottom = '20px';
            codeElement.style.padding = '10px';
            codeElement.style.borderBottom = '1px solid #444';
            outputDiv.appendChild(codeElement);

            // Add simulation run results
            const resultElement = document.createElement('div');
            resultElement.innerHTML = `
                <div style="color: #4CAF50; margin-top: 10px; margin-bottom: 10px;">
                    > Simulated operation output:</div>
                <pre style="color: #f8f8f8;">
#This is the result of Python code simulation run
#The actual operational results may vary

# Running ${filePath.split('/').pop()}...
print("Hello from Python Simulated environment!")

# Code execution completed
</pre>
            `;
            outputDiv.appendChild(resultElement);
        })
        .catch(error => {
            console.error('Error loading Python file:', error);
            const outputDiv = modal.querySelector('.python-output');
            outputDiv.innerHTML = `Error loading file: ${error.message}`;
        });
}

function isAuthorized() {
    return document.cookie.split(';').map(c => c.trim()).some(c => c.startsWith('auth='));
}

function logout() {
    document.cookie = 'auth=; Max-Age=0; path=/;';
    window.location.reload();
}

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();

    document.getElementById('prompt-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            createTask();
        }
    });

    const historyToggle = document.getElementById('history-toggle');
    if (historyToggle) {
        historyToggle.addEventListener('click', () => {
            const historyPanel = document.getElementById('history-panel');
            if (historyPanel) {
                historyPanel.classList.toggle('open');
                historyToggle.classList.toggle('active');
            }
        });
    }

    const clearButton = document.getElementById('clear-btn');
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            document.getElementById('prompt-input').value = '';
            document.getElementById('prompt-input').focus();
        });
    }

    // Add keyboard event listener to close modal boxes
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const imageModal = document.getElementById('image-modal');
            if (imageModal && imageModal.classList.contains('active')) {
                imageModal.classList.remove('active');
            }

            const pythonModal = document.getElementById('python-modal');
            if (pythonModal && pythonModal.classList.contains('active')) {
                pythonModal.classList.remove('active');
            }

            const configModal = document.getElementById('config-modal');
            if (configModal && configModal.classList.contains('active') && !isConfigRequired()) {
                configModal.classList.remove('active');
            }
        }
    });

});

function isConfigRequired() {
    return false;
}

function createHumanRequestElement(data, taskId) {
    // Сначала добавляем обычный элемент в лог для истории
    const logElement = document.createElement('div');
    logElement.className = 'step-item ask_human';

    const question = typeof data.result === 'object' ? data.result.question : data.result;
    const requestId = typeof data.result === 'object' ? data.result.request_id : null;

    if (!requestId) {
        console.error('No request_id found in ask_human data:', data);
        logElement.innerHTML = `
            <div class="log-line">
                <span class="log-prefix">💬 [${new Date().toLocaleTimeString()}] Question for User:</span>
                <pre>Error: No request ID found</pre>
            </div>
        `;
        return logElement;
    }

    // Добавляем элемент в лог
    logElement.innerHTML = `
        <div class="log-line">
            <span class="log-prefix">💬 [${new Date().toLocaleTimeString()}] Question for User:</span>
            <div class="question-content">
                <pre>${question}</pre>
                <em style="color: #666; font-size: 0.9em;">Waiting for user response...</em>
            </div>
        </div>
    `;

    // Создаем модальное окно
    showAskHumanModal(question, requestId, taskId);

    return logElement;
}

function showAskHumanModal(question, requestId, taskId) {
    // Удаляем существующие модальные окна ask_human
    const existingModal = document.getElementById('ask-human-modal');
    if (existingModal) {
        existingModal.remove();
    }

    const responseId = `response_${requestId}`;

    // Создаем модальное окно
    const modal = document.createElement('div');
    modal.id = 'ask-human-modal';
    modal.innerHTML = `
        <div class="ask-human-overlay">
            <div class="ask-human-modal">
                <div class="ask-human-header">
                    <h3>💬 Question from Agent</h3>
                    <div class="ask-human-time">${new Date().toLocaleTimeString()}</div>
                </div>
                <div class="ask-human-question">
                    <div class="question-text">${question}</div>
                </div>
                <div class="ask-human-form">
                    <textarea
                        id="${responseId}"
                        placeholder="Enter your response..."
                        rows="4"
                        autofocus
                    ></textarea>
                    <div class="ask-human-buttons">
                        <button
                            class="btn-primary"
                            onclick="respondToHumanModal('${taskId}', '${requestId}', '${responseId}')"
                        >
                            ✓ Send Response
                        </button>
                        <button
                            class="btn-secondary"
                            onclick="respondToHumanModal('${taskId}', '${requestId}', '${responseId}', 'skip')"
                        >
                            ⏭ Skip
                        </button>
                    </div>
                </div>
                <div class="ask-human-footer">
                    <small>Agent is waiting for your response to continue</small>
                </div>
            </div>
        </div>
    `;

    // Добавляем стили, если их еще нет
    if (!document.getElementById('ask-human-styles')) {
        const styles = document.createElement('style');
        styles.id = 'ask-human-styles';
        styles.textContent = `
            .ask-human-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10000;
                animation: askHumanFadeIn 0.3s ease-out;
            }

            .ask-human-modal {
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                max-width: 600px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                animation: askHumanSlideIn 0.3s ease-out;
            }

            .ask-human-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 12px 12px 0 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .ask-human-header h3 {
                margin: 0;
                font-size: 1.3em;
            }

            .ask-human-time {
                font-size: 0.9em;
                opacity: 0.9;
            }

            .ask-human-question {
                padding: 25px;
                border-bottom: 1px solid #eee;
            }

            .question-text {
                font-size: 1.1em;
                line-height: 1.6;
                color: #333;
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
            }

            .ask-human-form {
                padding: 25px;
            }

            .ask-human-form textarea {
                width: 100%;
                padding: 12px;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                font-size: 1em;
                line-height: 1.5;
                resize: vertical;
                margin-bottom: 15px;
                transition: border-color 0.3s ease;
            }

            .ask-human-form textarea:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }

            .ask-human-buttons {
                display: flex;
                gap: 10px;
                justify-content: flex-end;
            }

            .ask-human-buttons button {
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                font-size: 1em;
                cursor: pointer;
                transition: all 0.3s ease;
                font-weight: 500;
            }

            .btn-primary {
                background: #667eea;
                color: white;
            }

            .btn-primary:hover {
                background: #5a6fd8;
                transform: translateY(-1px);
            }

            .btn-secondary {
                background: #6c757d;
                color: white;
            }

            .btn-secondary:hover {
                background: #545b62;
                transform: translateY(-1px);
            }

            .ask-human-footer {
                padding: 15px 25px;
                background: #f8f9fa;
                color: #6c757d;
                text-align: center;
                border-radius: 0 0 12px 12px;
            }

            @keyframes askHumanFadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            @keyframes askHumanSlideIn {
                from {
                    opacity: 0;
                    transform: translateY(-50px) scale(0.95);
                }
                to {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }

            @keyframes askHumanFadeOut {
                from { opacity: 1; }
                to { opacity: 0; }
            }
        `;
        document.head.appendChild(styles);
    }

    document.body.appendChild(modal);

    // Фокусируемся на поле ввода
    setTimeout(() => {
        const textarea = document.getElementById(responseId);
        if (textarea) {
            textarea.focus();
        }
    }, 100);

    // Закрытие по Escape
    const handleEscape = (e) => {
        if (e.key === 'Escape') {
            // Можно добавить подтверждение закрытия
            if (confirm('Close without answering? (will be considered as skip)')) {
                respondToHumanModal(taskId, requestId, responseId, 'skip');
            }
        }
    };

    document.addEventListener('keydown', handleEscape);
    modal.addEventListener('remove', () => {
        document.removeEventListener('keydown', handleEscape);
    });
}

async function respondToHumanModal(taskId, requestId, responseElementId, action = 'respond') {
    const responseElement = document.getElementById(responseElementId);
    let response;

    if (action === 'skip') {
        response = 'User chose to skip this question.';
    } else {
        response = responseElement ? responseElement.value.trim() : '';
        if (!response) {
            // Показываем ошибку в модальном окне
            showModalError('Please enter a response or click "Skip"');
            return;
        }
    }

    // Показываем индикатор загрузки
    showModalLoading();

    try {
        const result = await fetch(`/tasks/${taskId}/respond`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                request_id: requestId,
                response: response
            })
        });

        if (result.ok) {
            // Показываем успех и закрываем модальное окно
            showModalSuccess(action === 'skip' ? '✓ Question skipped' : '✓ Response sent successfully');

            // Обновляем элемент в логе
            updateLogElement(requestId, response, action);

            // Закрываем модальное окно через 1.5 сек
            setTimeout(() => {
                closeAskHumanModal();
            }, 1500);

        } else {
            const errorData = await result.json();
            showModalError(`Error: ${errorData.detail || 'Failed to send response'}`);
        }
    } catch (error) {
        console.error('Error sending response:', error);
        showModalError('Network error. Please try again.');
    }
}

// Функция для старого интерфейса (совместимость)
async function respondToHuman(taskId, requestId, responseElementId, action = 'respond') {
    const responseElement = document.getElementById(responseElementId);
    let response;

    if (action === 'skip') {
        response = 'User chose to skip this question.';
    } else {
        response = responseElement ? responseElement.value.trim() : '';
        if (!response) {
            alert('Please enter a response or click Skip.');
            return;
        }
    }

    try {
        const result = await fetch(`/tasks/${taskId}/respond`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                request_id: requestId,
                response: response
            })
        });

        if (result.ok) {
            // Disable the form after successful response
            if (responseElement) {
                responseElement.disabled = true;
            }
            const buttons = document.querySelectorAll(`button[onclick*="${requestId}"]`);
            buttons.forEach(button => {
                button.disabled = true;
                button.style.opacity = '0.5';
            });

            // Add confirmation message
            const requestContainer = responseElement?.closest('.human-request');
            if (requestContainer) {
                const confirmMsg = document.createElement('div');
                confirmMsg.style.cssText = 'color: green; margin-top: 10px; font-weight: bold;';
                confirmMsg.textContent = action === 'skip' ? '✓ Question skipped' : '✓ Response sent successfully';
                requestContainer.appendChild(confirmMsg);
            }
        } else {
            const errorData = await result.json();
            alert(`Error: ${errorData.detail || 'Failed to send response'}`);
        }
    } catch (error) {
        console.error('Error sending response:', error);
        alert('Error sending response. Please try again.');
    }
}

function showModalError(message) {
    const modal = document.getElementById('ask-human-modal');
    if (!modal) return;

    const footer = modal.querySelector('.ask-human-footer');
    if (footer) {
        footer.innerHTML = `<div style="color: #dc3545; font-weight: bold;">❌ ${message}</div>`;
        footer.style.background = '#f8d7da';
    }
}

function showModalLoading() {
    const modal = document.getElementById('ask-human-modal');
    if (!modal) return;

    const buttons = modal.querySelectorAll('.ask-human-buttons button');
    buttons.forEach(button => {
        button.disabled = true;
        button.style.opacity = '0.5';
    });

    const footer = modal.querySelector('.ask-human-footer');
    if (footer) {
        footer.innerHTML = '<div style="color: #007bff;">⏳ Sending response...</div>';
        footer.style.background = '#d1ecf1';
    }
}

function showModalSuccess(message) {
    const modal = document.getElementById('ask-human-modal');
    if (!modal) return;

    const footer = modal.querySelector('.ask-human-footer');
    if (footer) {
        footer.innerHTML = `<div style="color: #155724; font-weight: bold;">${message}</div>`;
        footer.style.background = '#d4edda';
    }
}

function updateLogElement(requestId, response, action) {
    // Находим элемент в логе и обновляем его
    const logElements = document.querySelectorAll('.step-item.ask_human');
    for (const element of logElements) {
        const content = element.textContent;
        if (content.includes('Waiting for user response')) {
            const responseText = action === 'skip' ? '(skipped)' : `"${response}"`;
            element.querySelector('em').textContent = `User response: ${responseText}`;
            element.querySelector('em').style.color = '#28a745';
            break;
        }
    }
}

function closeAskHumanModal() {
    const modal = document.getElementById('ask-human-modal');
    if (modal) {
        modal.style.animation = 'askHumanFadeOut 0.3s ease-out forwards';
        setTimeout(() => {
            modal.remove();
        }, 300);
    }
}

async function cancelTask(taskId) {
    if (!confirm('Are you sure you want to cancel this task?')) {
        return;
    }

    try {
        const response = await fetch(`/tasks/${taskId}/cancel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const data = await response.json();
            console.log('Task cancelled successfully:', data);

            // Update UI to show task was cancelled
            const taskElement = document.querySelector(`[data-task-id="${taskId}"]`);
            if (taskElement) {
                const statusElement = taskElement.querySelector('.task-status');
                if (statusElement) {
                    statusElement.textContent = 'cancelled';
                    statusElement.className = 'task-status status-cancelled';
                }

                // Hide cancel button
                hideCancelButton();
            }
        } else {
            const error = await response.json();
            alert(`Task cancellation error: ${error.detail || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error cancelling task:', error);
        alert(`Network error: ${error.message}`);
    }
}

function cancelCurrentTask() {
    if (!currentTaskId) {
        alert('No active task to cancel');
        return;
    }

    cancelTask(currentTaskId);
}

function showCancelButton() {
    const cancelBtn = document.getElementById('cancel-task-btn');
    if (cancelBtn) {
        cancelBtn.style.display = 'inline-block';
    }
}

function hideCancelButton() {
    const cancelBtn = document.getElementById('cancel-task-btn');
    if (cancelBtn) {
        cancelBtn.style.display = 'none';
    }
}
