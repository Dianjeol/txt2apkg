document.getElementById('convertForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('file', document.getElementById('file').files[0]);
    formData.append('deck_name', document.getElementById('deck_name').value);
    
    const status = document.getElementById('status');
    status.textContent = 'Konvertierung läuft...';
    
    try {
        const response = await fetch('/convert', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = document.getElementById('deck_name').value + '.apkg';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            status.textContent = 'Konvertierung erfolgreich!';
        } else {
            const error = await response.text();
            status.textContent = 'Fehler: ' + error;
        }
    } catch (error) {
        console.error('Error:', error);
        status.textContent = 'Fehler bei der Konvertierung';
    }
});
