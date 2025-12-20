# 🧪 Test Tabella Unificata - Checklist

## ✅ Test da Eseguire

### 1. Test Auto-Espansione Sezione

#### Test Misurazioni

1. [ ] Apri la console del browser (F12)
2. [ ] Esegui una misurazione qualsiasi
3. [ ] Verifica nei log della console:
   - `🔍 [UNIFIED] Tentativo apertura sezione DATI ANALISI...`
   - `✅ [UNIFIED] Sezione DATI ANALISI aperta automaticamente`
4. [ ] Verifica che la sezione "📊 DATI ANALISI" si espanda
5. [ ] Verifica che il tab "📏 Misurazioni" mostri i dati

#### Test Landmarks

1. [ ] Attiva i landmarks
2. [ ] Clicca su un punto del viso
3. [ ] Verifica nei log della console i messaggi di apertura
4. [ ] Verifica che la sezione "📊 DATI ANALISI" si espanda
5. [ ] Cambia al tab "🎯 Landmarks"
6. [ ] Verifica che il landmark appaia immediatamente nella tabella

#### Test Debug

1. [ ] Carica un video o avvia l'analisi
2. [ ] Quando arrivano i frame debug, verifica nei log
3. [ ] Verifica che la sezione "📊 DATI ANALISI" si espanda
4. [ ] Cambia al tab "🐛 Debug"
5. [ ] Verifica che i frame siano visibili

### 2. Test Click Righe Debug

1. [ ] Assicurati di essere nel tab "🐛 Debug"
2. [ ] Assicurati che ci siano dati debug nella tabella
3. [ ] Clicca su una riga della tabella
4. [ ] **Verifica che l'immagine nel canvas cambi** al frame selezionato
5. [ ] Verifica che la riga cliccata si evidenzi
6. [ ] Clicca su un'altra riga
7. [ ] Verifica che l'highlight si sposti sulla nuova riga
8. [ ] Verifica che l'immagine nel canvas cambi di nuovo

### 3. Test Interfaccia Pulita

1. [ ] Vai al tab "📏 Misurazioni"
   - [ ] Verifica che NON ci siano controlli sotto la tabella
2. [ ] Vai al tab "🎯 Landmarks"
   - [ ] Verifica che NON ci siano controlli di paginazione
3. [ ] Vai al tab "🐛 Debug"
   - [ ] Verifica che NON ci siano pulsanti "Pulisci", "Ripristina UI", ecc.

## 🐛 Debugging

### Se la sezione non si apre automaticamente:

1. Apri la console del browser
2. Cerca questi log:

   ```
   🔍 [UNIFIED] Tentativo apertura sezione DATI ANALISI...
   🔍 [UNIFIED] Trovate X sezioni nel DOM
   🔍 [UNIFIED] Sezione 0: "..."
   🔍 [UNIFIED] Sezione 1: "..."
   ```

3. Se vedi `⚠️ [UNIFIED] Sezione DATI ANALISI NON trovata nel DOM!`:

   - Verifica che la sezione esista nell'HTML
   - Controlla il nome esatto del pulsante (deve contenere "📊" e "DATI ANALISI")

4. Se vedi `✅ [UNIFIED] Sezione DATI ANALISI aperta` ma non si vede:
   - Prova a ricaricare la pagina (Ctrl+F5)
   - Verifica che non ci siano errori CSS

### Se il click sulle righe debug non funziona:

1. Verifica nella console:

   ```
   ✅ Tabella unificata aggiornata: Debug con X righe
   ```

2. Ispeziona una riga della tabella debug:

   - Verifica che abbia `style="cursor: pointer"`
   - Verifica che l'evento click sia registrato

3. Verifica che esista `window.currentBestFrames`:

   ```javascript
   // Nella console
   console.log(window.currentBestFrames);
   ```

4. Verifica che esista la funzione `showFrameInMainCanvas`:
   ```javascript
   // Nella console
   typeof showFrameInMainCanvas;
   // Dovrebbe restituire "function"
   ```

## 📊 Log Attesi

### Quando aggiungi una misurazione:

```
📊 Tabella misurazioni aggiornata: 1 risultati
🔍 [UNIFIED] Tentativo apertura sezione DATI ANALISI...
🔍 [UNIFIED] Trovate 3 sezioni nel DOM
🔍 [UNIFIED] Sezione 0: "📹 ANTEPRIMA"
🔍 [UNIFIED] Sezione 1: "📊 DATI ANALISI"
🔍 [UNIFIED] Sezione DATI ANALISI trovata! Display attuale: none
✅ [UNIFIED] Sezione DATI ANALISI aperta automaticamente
```

### Quando aggiungi un landmark:

```
📍 Landmark 33 (Left Eye Outer Corner) aggiunto alla tabella: (123.4, 256.8)
🔍 [UNIFIED] Tentativo apertura sezione DATI ANALISI...
✅ [UNIFIED] Sezione DATI ANALISI aperta automaticamente
```

### Quando arrivano frame debug:

```
📊 Tabella debug aggiornata con 10 frame
🔍 [UNIFIED] Tentativo apertura sezione DATI ANALISI...
✅ [UNIFIED] Sezione DATI ANALISI aperta automaticamente
✅ Tabella unificata aggiornata: Debug con 10 righe
```

## 🎯 Risultati Attesi

✅ **Sezione Auto-Espansione:** La sezione "📊 DATI ANALISI" si apre automaticamente quando:

- Viene aggiunta una misurazione
- Viene cliccato un landmark
- Arrivano dati debug

✅ **Click Righe Debug:** Cliccando su una riga del tab Debug:

- L'immagine nel canvas cambia al frame selezionato
- La riga si evidenzia

✅ **Interfaccia Pulita:** Nessun controllo visibile sotto le tabelle

## 📝 Note

- I log con prefisso `[UNIFIED]` sono stati aggiunti per debug
- Il timeout di 100-150ms serve per sincronizzazione DOM
- La variabile `window.currentBestFrames` contiene i dati dei frame debug
- Gli event listener sono ri-aggiunti quando si copia la tabella

---

**Data Test:** ********\_********

**Risultato:** ⬜ Tutti i test passati | ⬜ Alcuni problemi | ⬜ Molti problemi

**Note:**

---

---

---
