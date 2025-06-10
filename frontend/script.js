// API endpoint - alle API calls gehen jetzt über /api/
const API_URL = '/api';

// Load users on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadUsers();
});

async function loadUsers() {
    try {
        console.log('Loading users from:', `${API_URL}/users`);
        const response = await fetch(`${API_URL}/users`);
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Users data:', data);
        
        const userSelect = document.getElementById('user-select');
        if (data.users && data.users.length > 0) {
            data.users.forEach(user => {
                const option = document.createElement('option');
                option.value = user;
                option.textContent = user;
                userSelect.appendChild(option);
            });
        } else {
            console.error('No users found in response');
        }
    } catch (error) {
        console.error('Error loading users:', error);
        alert('Fehler beim Laden der Benutzer: ' + error.message);
    }
}

// Process button click
document.getElementById('process-btn').addEventListener('click', async () => {
    const user = document.getElementById('user-select').value;
    if (!user) {
        alert('Bitte wählen Sie einen Benutzer aus');
        return;
    }
    
    const halunderText = document.getElementById('halunder-text').value;
    if (!halunderText.trim()) {
        alert('Bitte geben Sie einen Halunder Text ein');
        return;
    }
    
    // Show status
    const statusSection = document.getElementById('status');
    const statusMessage = document.getElementById('status-message');
    const progressBar = document.querySelector('.progress-bar');
    const progressFill = document.querySelector('.progress-fill');
    
    statusSection.classList.remove('hidden');
    progressBar.classList.remove('hidden');
    statusMessage.textContent = 'Text wird verarbeitet...';
    progressFill.style.width = '20%';
    
    // Prepare data
    const data = {
        halunder_text: halunderText,
        german_text: document.getElementById('german-text').value,
        translation_aids: document.getElementById('translation-aids').value,
        idiom_explanations: document.getElementById('idiom-explanations').value,
        source_title: document.getElementById('source-title').value,
        source_author: document.getElementById('source-author').value,
        source_page: document.getElementById('source-page').value,
        source_date: document.getElementById('source-date').value,
        proofread: document.getElementById('proofread').checked,
        proofread_by: document.getElementById('proofread-by').value,
        added_by: user
    };
    
    try {
        progressFill.style.width = '50%';
        statusMessage.textContent = 'Texttyp wird analysiert...';
        
        const response = await fetch(`${API_URL}/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        progressFill.style.width = '80%';
        statusMessage.textContent = 'Sätze werden extrahiert...';
        
        const result = await response.json();
        
        progressFill.style.width = '100%';
        statusMessage.textContent = 'Fertig!';
        
        // Show results
        showResults(result);
        
        // Clear form
        document.getElementById('halunder-text').value = '';
        document.getElementById('german-text').value = '';
        document.getElementById('translation-aids').value = '';
        document.getElementById('idiom-explanations').value = '';
        
    } catch (error) {
        statusMessage.innerHTML = `<div class="error-message">Fehler: ${error.message}</div>`;
        console.error('Processing error:', error);
    }
});

function showResults(result) {
    const resultsSection = document.getElementById('results');
    const resultsContent = document.getElementById('results-content');
    
    resultsSection.classList.remove('hidden');
    
    let html = '<div class="success-message">Text erfolgreich verarbeitet!</div>';
    
    html += `
        <p><strong>Textsprache:</strong> ${result.text_type?.primary_language || 'Halunder'}</p>
        <p><strong>Extrahierte Sätze:</strong> ${result.sentences_extracted}</p>
        <p><strong>Übersetzungshilfen:</strong> ${result.translation_aids_extracted}</p>
        <p><strong>Idiom-Erklärungen:</strong> ${result.idioms_extracted || 0}</p>
    `;
    
    if (result.has_parallel_text) {
        html += `
            <div class="match-notification">
                <strong>Paralleler Text erkannt!</strong><br>
                Halunder und deutsche Sätze wurden gematcht.
            </div>
        `;
    }
    
    resultsContent.innerHTML = html;
}

// Export button with proper download handling
document.getElementById('export-btn').addEventListener('click', async () => {
    try {
        // Show loading state
        const exportBtn = document.getElementById('export-btn');
        const originalText = exportBtn.textContent;
        exportBtn.textContent = 'Exportiere...';
        exportBtn.disabled = true;
        
        // Fetch the CSV file
        const response = await fetch(`${API_URL}/export`, {
            method: 'GET',
            headers: {
                'Accept': 'text/csv'
            }
        });
        
        if (!response.ok) {
            throw new Error(`Export failed: ${response.statusText}`);
        }
        
        // Get filename from Content-Disposition header if available
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'halunder_corpus.csv';
        if (contentDisposition) {
            const match = contentDisposition.match(/filename="?(.+)"?/);
            if (match) {
                filename = match[1];
            }
        }
        
        // Get the blob
        const blob = await response.blob();
        
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        
        // Append to body and trigger download
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        setTimeout(() => {
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }, 100);
        
        // Show success message
        const statusMessage = document.getElementById('status-message');
        const statusSection = document.getElementById('status');
        statusSection.classList.remove('hidden');
        statusMessage.innerHTML = `<div class="success-message">Export erfolgreich heruntergeladen: ${filename}</div>`;
        
        // Hide success message after 3 seconds
        setTimeout(() => {
            statusSection.classList.add('hidden');
        }, 3000);
        
    } catch (error) {
        alert('Export fehlgeschlagen: ' + error.message);
        console.error('Export error:', error);
    } finally {
        // Reset button
        const exportBtn = document.getElementById('export-btn');
        exportBtn.textContent = originalText || 'Korpus exportieren (CSV)';
        exportBtn.disabled = false;
    }
});