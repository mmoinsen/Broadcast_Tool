const modalMessage = document.getElementById("messageModal");
const modalHistory = document.getElementById("historyModal");
const historyListContainer = document.getElementById("historyMessagesList");
const textArea = document.getElementById("msgText");

// Dummy Daten für den Test, falls keine DB da ist
let globalData = [
    { time: "10:00", message: "Beispiel Nachricht 1" },
    { time: "11:30", message: "Beispiel Nachricht 2" }
];

// Funktion zum Öffnen des Message Modals
function openMessageModal() {
  modalMessage.style.display = "flex";
}

// Funktion zum Öffnen des History Modals
function openHistoryModal() {
  modalHistory.style.display = "flex";
  // Hier könnten wir auch erst getData() aufrufen
  loadHistoryData();
}

// Daten anzeigen
function loadHistoryData(){
    historyListContainer.innerHTML = "";
    
    // Wir nutzen hier 'globalData' statt dem unbekannten 'data'
    if (globalData && globalData.length > 0) {
        globalData.forEach(element => {
            const htmlItem = `
                <div class="history-item">
                    <span class="history-time">${element.time}</span>
                    <div class="history-text">${element.message}</div>
                </div>
            `;
            historyListContainer.insertAdjacentHTML("beforeend", htmlItem);
        });
    } else {
        historyListContainer.innerHTML = "<p style='text-align:center; color:#888;'>Keine Nachrichten vorhanden.</p>";
    }
}

// Schließt alle Modals
function closeAllModals() {
  modalMessage.style.display = "none";
  modalHistory.style.display = "none";
  if (textArea) textArea.value = "";
}

// Schließen beim Klick neben das Fenster
window.onclick = function (event) {
  if (event.target == modalMessage || event.target == modalHistory) {
    closeAllModals();
  }
};