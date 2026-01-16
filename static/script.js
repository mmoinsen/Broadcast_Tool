const modalMessage = document.getElementById("messageModal");
const modalHistory = document.getElementById("historyModal");
const historyListContainer = document.getElementById("historyMessagesList");
const form = document.getElementById("messageForm");
const textArea = document.getElementById("msgText");

// --- FENSTER ÖFFNEN ---

function openMessageModal() {
  if(modalMessage) modalMessage.style.display = "flex";
}

function openHistoryModal() {
  if(modalHistory) modalHistory.style.display = "flex";
  // Jetzt rufen wir die ECHTEN Daten ab
  loadHistoryData();
}

// --- DATEN LADEN (VON PYTHON) ---
async function loadHistoryData() {
    if(historyListContainer) historyListContainer.innerHTML = "Lade Daten...";

    try {
        // Hier rufen wir die neue Python-Route auf
        const response = await fetch('/get_history'); 
        const data = await response.json();

        // Container leeren
        historyListContainer.innerHTML = "";

        if (data.length > 0) {
            data.forEach(element => {
                // Wir nutzen 'element.time' und 'element.message' wie in Python definiert
                const htmlItem = `
                    <div class="history-item">
                        <span class="history-time">${element.time}</span>
                        <div class="history-text">${element.message}</div>
                        <button class="delete-btn" onclick="deleteMessage(${element.id})" title="Löschen">
                        &#128465;
                        </button>
                    </div>
                `;
                historyListContainer.insertAdjacentHTML("beforeend", htmlItem);
            });
        } else {
            historyListContainer.innerHTML = "<p style='padding:20px; text-align:center;'>Noch keine Nachrichten vorhanden.</p>";
        }

    } catch (error) {
        console.error("Fehler beim Laden:", error);
        historyListContainer.innerHTML = "<p style='color:red; text-align:center;'>Fehler beim Laden der Daten.</p>";
    }
}
async function deleteMessage(id) {
    // 1. Bestätigung abfragen
    const check = confirm("Möchtest du diese Nachricht wirklich löschen?");
    
    if (check) {
        try {
            // 2. Befehl an Python senden
            const response = await fetch(`/delete_message/${id}`, {
                method: 'DELETE'
            });

            const result = await response.json();
            if (result.success) {
                // 3. Wenn erfolgreich, Liste neu laden
                loadHistoryData();
            } else {
                alert("Fehler beim Löschen: " + result.message);
            }
        } catch (error) {
            console.error("Fehler:", error);
            alert("Verbindungsfehler beim Löschen.");
        }
    }
}

// --- FENSTER SCHLIEßEN ---
function closeAllModals() {
  if(modalMessage) modalMessage.style.display = "none";
  if(modalHistory) modalHistory.style.display = "none";
  // Textfeld leeren
  if (textArea) textArea.value = "";
}

window.onclick = function (event) {
  if (event.target == modalMessage || event.target == modalHistory) {
    closeAllModals();
  }
};