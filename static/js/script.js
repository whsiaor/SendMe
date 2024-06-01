// script.js

var socket = io.connect('wss://sendme.aussievitamin.com');

socket.on('connect', function() {
    console.log('Connected to server');
});

socket.on('disconnect', function() {
    console.log('Disconnected from server');
});

socket.on('new_message', function (data) {
    addNewItem(data);
});

socket.on('new_file', function (data) {
    addNewItem(data);
});

socket.on('delete_batch', function (data) {
    const batchId = data.batch_id;
    const batchElement = document.querySelector(`[data-batch-id="${batchId}"]`);
    if (batchElement) {
        batchElement.remove();
    }
});

function addNewItem(data) {
    const container = document.getElementById('items-container');
    const batchId = data.batch_id;
    let batchElement = document.querySelector(`[data-batch-id="${batchId}"]`);

    if (!batchElement) {
        batchElement = document.createElement('div');
        batchElement.classList.add('bg-dark', 'text-break', 'pl-3', 'mb-3', 'rounded-lg');
        batchElement.setAttribute('data-batch-id', batchId);

        const header = document.createElement('div');
        header.classList.add('d-flex', 'justify-content-between', 'bd-highlight', 'text-muted', 'fw-lighter');
        header.innerHTML = `<p><small>${data.timestamp}</small></p>
                            <div class="bd-highlight">
                                <form method="POST" action="/delete_batch/${batchId}" style="display:inline;">
                                    <button class="btn btn-dark btn-sm border-0" type="submit"><i class="bi bi-x text-muted"></i></button>
                                </form>
                            </div>`;
        batchElement.appendChild(header);

        container.insertBefore(batchElement, container.firstChild);
    }

    const itemElement = document.createElement('div');
    itemElement.classList.add('d-flex', 'pb-3', 'bd-highlight');

    if (data.type === 'message') {
        itemElement.innerHTML = `<div class="mr-auto bd-highlight text-light align-self-center">${data.message}</div>
                                 <div class="p-2 bd-highlight align-self-center">
                                     <button class="btn btn-dark border-0" onclick="copyToClipboard('${data.message}', this)"><i class="bi bi-clipboard text-info btn-lg"></i></button>
                                 </div>`;
    } else if (data.type === 'file') {
        itemElement.innerHTML = `<div class="mr-auto bd-highlight text-light align-self-center">
                                     <img src="${data.url}" height="80px" alt="Image">
                                     ${data.name}
                                 </div>
                                 <div class="p-2 bd-highlight align-self-center">
                                     <form method="GET" action="/downloads/${data.name}" style="display:inline;">
                                         <button class="btn btn-dark border-0" type="submit"><i class="bi bi-download text-info btn-lg"></i></button>
                                     </form>
                                 </div>`;
    }

    batchElement.appendChild(itemElement);
}

function copyToClipboard(text, button) {
    navigator.clipboard.writeText(text)
        .then(() => {
            const originalIcon = button.innerHTML;
            button.innerHTML = '<i class="bi bi-clipboard-check text-success btn-lg"></i>';

            setTimeout(() => {
                button.innerHTML = originalIcon;
            }, 2000);
        })
        .catch(err => {
            console.error('Failed to copy text: ', err);
        });
}


function previewFile() {
    const fileInput = document.getElementById('file-input');
    const filePreview = document.getElementById('file-preview');

    filePreview.innerHTML = ''; // Clear previous previews

    const files = fileInput.files;
    for (const file of files) {
        const fileName = document.createElement('p');
        fileName.textContent = file.name;
        filePreview.appendChild(fileName);
    }
}

document.getElementById('message').addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        document.getElementById('uploadForm').submit();
    }
});
