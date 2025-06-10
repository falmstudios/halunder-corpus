const API_URL = '/api';
let allSentences = [];
let filteredSentences = [];
let currentPage = 1;
const itemsPerPage = 50;
let currentEditId = null;

document.addEventListener('DOMContentLoaded', async () => {
    await loadAllSentences();
    setupEventListeners();
});

function setupEventListeners() {
    // Filters
    document.getElementById('apply-filters').addEventListener('click', applyFilters);
    document.getElementById('reset-filters').addEventListener('click', resetFilters);
    
    // Pagination
    document.getElementById('prev-page').addEventListener('click', () => changePage(-1));
    document.getElementById('next-page').addEventListener('click', () => changePage(1));
    
    // Export
    document.getElementById('export-btn').addEventListener('click', exportCSV);
    
    // Modal
    document.querySelector('.close').addEventListener('click', closeModal);
    document.getElementById('save-changes').addEventListener('click', saveChanges);
    document.getElementById('cancel-edit').addEventListener('click', closeModal);
}

async function loadAllSentences() {
    try {
        const response = await fetch(`${API_URL}/all-sentences`);
        const data = await response.json();
        allSentences = data.sentences;
        filteredSentences = [...allSentences];
        displaySentences();
    } catch (error) {
        console.error('Error loading sentences:', error);
        alert('Fehler beim Laden der Sätze');
    }
}

function displaySentences() {
    const tbody = document.getElementById('sentences-tbody');
    tbody.innerHTML = '';
    
    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageSentences = filteredSentences.slice(start, end);
    
    pageSentences.forEach((sentence, index) => {
        const row = document.createElement('tr');
        const confidence = Math.round((sentence.match_confidence || 0) * 100);
        const confidenceClass = getConfidenceClass(confidence);
        
        row.innerHTML = `
            <td>${start + index + 1}</td>
            <td class="${!sentence.halunder_text ? 'empty-cell' : ''}">
                ${sentence.halunder_text || '(leer)'}
            </td>
            <td class="${!sentence.german_text ? 'empty-cell' : ''}">
                ${sentence.german_text || '(leer)'}
            </td>
            <td class="confidence-cell ${confidenceClass}">
                ${confidence}%
            </td>
            <td>${sentence.source_title || '-'}</td>
            <td>${sentence.reasoning || '-'}</td>
            <td>
                <button class="edit-btn" onclick="editSentence('${sentence.id}')">
                    Bearbeiten
                </button>
            </td>
        `;
        
        tbody.appendChild(row);
    });
    
    updatePagination();
}

function getConfidenceClass(confidence) {
    if (confidence >= 80) return 'confidence-high';
    if (confidence >= 50) return 'confidence-medium';
    return 'confidence-low';
}

function updatePagination() {
    const totalPages = Math.ceil(filteredSentences.length / itemsPerPage);
    document.getElementById('page-info').textContent = 
        `Seite ${currentPage} von ${totalPages} (${filteredSentences.length} Einträge)`;
    
    document.getElementById('prev-page').disabled = currentPage === 1;
    document.getElementById('next-page').disabled = currentPage === totalPages;
}

function changePage(direction) {
    currentPage += direction;
    displaySentences();
}

function applyFilters() {
    const minConfidence = parseInt(document.getElementById('confidence-filter').value);
    const sourceFilter = document.getElementById('source-filter').value.toLowerCase();
    const incompleteOnly = document.getElementById('incomplete-filter').checked;
    
    filteredSentences = allSentences.filter(sentence => {
        // Confidence filter
        if ((sentence.match_confidence || 0) * 100 < minConfidence) return false;
        
        // Source filter
        if (sourceFilter && !(sentence.source_title || '').toLowerCase().includes(sourceFilter)) {
            return false;
        }
        
        // Incomplete filter
        if (incompleteOnly && sentence.halunder_text && sentence.german_text) {
            return false;
        }
        
        return true;
    });
    
    currentPage = 1;
    displaySentences();
}

function resetFilters() {
    document.getElementById('confidence-filter').value = '0';
    document.getElementById('source-filter').value = '';
    document.getElementById('incomplete-filter').checked = false;
    
    filteredSentences = [...allSentences];
    currentPage = 1;
    displaySentences();
}

function editSentence(sentenceId) {
    currentEditId = sentenceId;
    const sentence = allSentences.find(s => s.id === sentenceId);
    
    if (sentence) {
        document.getElementById('modal-halunder').value = sentence.halunder_text || '';
        document.getElementById('modal-german').value = sentence.german_text || '';
        document.getElementById('modal-confidence').value = Math.round((sentence.match_confidence || 0) * 100);
        document.getElementById('modal-reasoning').value = sentence.reasoning || '';
        
        document.getElementById('edit-modal').classList.remove('hidden');
    }
}

function closeModal() {
    document.getElementById('edit-modal').classList.add('hidden');
    currentEditId = null;
}

async function saveChanges() {
    if (!currentEditId) return;
    
    const updateData = {
        halunder_text: document.getElementById('modal-halunder').value,
        german_text: document.getElementById('modal-german').value,
        match_confidence: document.getElementById('modal-confidence').value / 100,
        reasoning: document.getElementById('modal-reasoning').value
    };
    
    try {
        const response = await fetch(`${API_URL}/sentences/${currentEditId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(updateData)
        });
        
        if (response.ok) {
            // Update local data
            const sentence = allSentences.find(s => s.id === currentEditId);
            Object.assign(sentence, updateData);
            
            closeModal();
            displaySentences();
            
            // Show success message
            const status = document.createElement('div');
            status.className = 'success-message';
            status.textContent = 'Änderungen gespeichert!';
            status.style.position = 'fixed';
            status.style.top = '20px';
            status.style.right = '20px';
            status.style.zIndex = '1001';
            document.body.appendChild(status);
            
            setTimeout(() => status.remove(), 3000);
        } else {
            throw new Error('Speichern fehlgeschlagen');
        }
    } catch (error) {
        alert('Fehler beim Speichern: ' + error.message);
    }
}

async function exportCSV() {
    try {
        const exportBtn = document.getElementById('export-btn');
        exportBtn.textContent = 'Exportiere...';
        exportBtn.disabled = true;
        
        const response = await fetch(`${API_URL}/export`, {
            method: 'GET',
            headers: {
                'Accept': 'text/csv'
            }
        });
        
        if (!response.ok) {
            throw new Error(`Export failed: ${response.statusText}`);
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `halunder_corpus_${new Date().toISOString().slice(0,10)}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        alert('Export fehlgeschlagen: ' + error.message);
    } finally {
        const exportBtn = document.getElementById('export-btn');
        exportBtn.textContent = 'CSV Exportieren';
        exportBtn.disabled = false;
    }
}

// Make editSentence global
window.editSentence = editSentence;