# AI Flashcards - Großes Update der Architektur (10. Mai 2026)

## 🎯 Hauptprobleme - GELÖST

### ❌ Problem 1: Kartenauswahl und Generierung funktioniert nicht
**Ursache**: Combo-Box-Logik war fehlerhaft, Kartengenerierung konnte nicht korrekt aufgerufen werden
**Lösung**: Vollständige Überarbeitung der UI mit intelligentem CardSelector

### ❌ Problem 2: Add-on funktioniert nur von der Startseite
**Ursache**: Keine Hooks für Kontextabhängigkeit registriert
**Lösung**: Neue kontextabhängige Funktionen, die überall in Anki funktionieren

### ❌ Problem 3: Keine Gruppierung von generierten Karten
**Ursache**: Jede Karte war isoliert, keine Parent-Child-Beziehungen
**Lösung**: Neues CardHierarchyManager-System mit persistenter Speicherung

### ❌ Problem 4: Keine automatische Unterscheidung zwischen AI und Manual
**Ursache**: Tag-System war zu einfach
**Lösung**: Erweitertes Tag-System mit hierarchischen Tags

---

## 🚀 Neu implementierte Systeme

### 1. Card Hierarchy Manager (`card_hierarchy.py`)

Verwaltet Beziehungen zwischen Karten:
- **Parent Cards**: Ursprungskarte (z.B. manuelle Karte)
- **Generated Cards**: Karten, die davon abgeleitet wurden
- **Groups**: Zusammenfassungen von verwandten Karten

Datenspeicherung: `hierarchy.json` im Profil-Verzeichnis persistiert alles

### 2. Verbessertes Tag-System (`tag_system.py`)

Neue Hierarchie-Tags für bessere Organisation:

#### Level 1: HERKUNFT
- `ai_from_text`, `ai_from_pdf`, `ai_from_slide`, `ai_from_screenshot`

#### Level 2: BEZIEHUNG
- `ai_parent_card`: Diese Karte hat Kinder
- `ai_generated`: Von AI erzeugt
- `ai_variant`: Alternative Version

#### Level 3: STATUS
- `ai_verified`: Best Practices erfüllt
- `ai_needs_review`: Benötigt Überprüfung

#### Level 4: KLASSIFIKATION
- `difficulty_easy/medium/hard`
- `subject_*` und `topic_*` aus Deck-Namen

### 3. Kontextabhängige AnkiService-Methoden (`anki_service.py`)

- `get_current_context_card()`: Findet intelligenteste Karte
- `get_currently_reviewed_card()`: Karte im Review-Modus
- `search_cards_with_tags()`: Flexible Tag-Suche
- `get_all_ai_generated_cards()`: Alle AI-Karten
- `get_manual_cards()`: Nur manuelle Karten

### 4. Neue CardSelector UI-Komponente (`ui_enhanced.py`)

Intelligente Kartenliste mit automatischer Kategorisierung - zeigt AI und manuelle Karten getrennt

### 5. Verbesserte UI mit Kontext-Awareness (`ui_enhanced.py`)

Neue EnhancedUI Klasse mit zwei Modi:

#### Modus 1: Hauptdialog (vollständiger Workflow)
- Tab 1: Karte verifizieren
- Tab 2: Varianten erstellen  
- Tab 3: Aus Medien generieren

#### Modus 2: Schnell-Dialog (Kontext-Bewusstsein) ⭐ NEU
Menü: Tools → AI Flashcards → "Quick AI Tools (Context-Aware)"
- Zeigt aktuelle Karte automatisch
- Schnelle Operationen ohne Lernsitzung zu unterbrechen

---

## 📁 Neue und veränderte Dateien

### Neu erstellt:
- `card_hierarchy.py` - CardHierarchyManager System
- `ui_enhanced.py` - Neue EnhancedUI Klasse

### Verändert:
- `__init__.py` - Neue Hook-Registrierung
- `tag_system.py` - Erweiterte Tag-Verwaltung
- `anki_service.py` - Kontextabhängige Methoden

---

## ✅ Was jetzt funktioniert

- ✅ Kartenauswahl mit intelligenter Filterung
- ✅ Kartengenerierung speichert Karten korrekt
- ✅ Automatische Unterscheidung AI vs Manual
- ✅ Gruppierung von Kartenfamilien
- ✅ Schnelle Operationen von überall in Anki
- ✅ Kontext-bewusste Vorschläge
- ✅ Persistente Hierarchie über Neustarts

---

## 🧪 Test-Anleitung

### Test 1: Menüeinträge sichtbar
```
Tools → AI Flashcards
Sollte anzeigen:
  ✓ Generate or Verify Cards (Hauptdialog)
  ✓ Quick AI Tools (Context-Aware) (Schnell-Dialog)
```

### Test 2: Kartenauswahl funktioniert
```
1. Öffnen Sie "Generate or Verify Cards"
2. Kartenliste sollte anzeigen, gruppiert nach:
   --- AI Generated ---
   [Deck] Karte...
   --- Manual ---
   [Deck] Karte...
3. Kartenwahl sollte funktionieren und Inhalt laden
```

### Test 3: Tags funktionieren
```
1. Generieren Sie 5 Karten aus Text
2. In Browser suchen: tag:ai_from_text → sollte alle anzeigen
3. Suchen: tag:ai_generated → sollte alle AI-Karten anzeigen
```

### Test 4: Kontext-Dialog beim Lernen
```
1. Starten Sie eine Lernsitzung
2. Karte wird angezeigt
3. Klicken: Tools → AI Flashcards → Quick AI Tools
4. Dialog sollte zeigen: "Current Card: [Deck] Frage..."
5. Klicken "Verify This Card" oder "Create Variants"
6. AI sollte verarbeiten und Ergebnisse anzeigen
```

### Test 5: Hierarchie-Persistenz
```
1. Generieren Sie 3 Karten aus Text
2. Schließen Sie Anki
3. Öffnen Sie Anki erneut
4. hierarchy.json sollte Gruppen persistent speichern
```

---

## 🔄 Beispiel-Workflows

### Workflow 1: Text zu Kartenfamilie
```
1. Tab 3: Text einfügen
2. "Generate Cards" klicken
3. 5 Karten generiert mit Tags: ai_from_text, ai_generated
4. Alle akzeptieren
5. System erstellt Gruppe mit 1. als Parent
6. Alle 5 unter dieser Gruppe organisiert
```

### Workflow 2: Quick Variations beim Lernen
```
1. Lernen Sie ein Deck
2. Karte wird angezeigt: "Was ist eine Mitochondrie?"
3. "Quick AI Tools" klicken
4. "Create Variants" klicken
5. AI generiert 3 alternative Versionen
6. Bestätigen und Hinzufügen
7. Lernsitzung setzt sich fort!
```

### Workflow 3: AI vs Manual trennen
```
Browser-Suche:
- tag:ai_generated → nur AI-Generierte
- -tag:ai_* → nur manuelle Karten
- tag:ai_parent_card → nur Parents mit Kindern
```

---

## 🔧 Installation

```bash
cd /Users/leonvonolnhausen/PycharmProjects/anki-add-ons
python scripts/build_all.py
# Anki neustarten
# Tools → AI Flashcards → Probieren Sie beide Optionen
```

Das System sollte jetzt vollständig funktionieren!

