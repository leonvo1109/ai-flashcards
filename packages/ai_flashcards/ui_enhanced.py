"""Enhanced UI system for AI Flashcards with context awareness and better organization."""

import asyncio
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from PyQt6.QtWidgets import (
    QApplication,
    QTextEdit,
    QPushButton,
    QComboBox,
    QLabel,
    QScrollArea,
    QWidget,
    QFileDialog,
    QCheckBox,
    QTabWidget,
    QSpinBox,
    QVBoxLayout,
    QHBoxLayout,
)
from aqt import mw
from aqt.qt import (
    QAction,
    QDialog,
    QDialogButtonBox,
    QEventLoop,
    QMenu,
    QTimer,
)
from aqt.utils import qconnect, showInfo, showWarning

from .llm.factory import build_provider
from .anki_service import AnkiService, CardInfo
from .card_services import (
    CardVerificationService,
    CardGenerationService,
    MultiTypeCards,
)
from .tag_system import TagManager
from .card_hierarchy import CardHierarchyManager


@dataclass
class UIState:
    menu: QMenu | None = None
    menu_actions: dict[str, QAction] = field(default_factory=dict)
    dialogs: dict[str, QDialog] = field(default_factory=dict)
    text_fields: dict[str, QTextEdit] = field(default_factory=dict)


class CardSelector:
    """Helper class to handle intelligent card selection with filtering."""

    def __init__(self, tag_manager: TagManager):
        self.tag_manager = tag_manager
        self.selected_card_id: int | None = None

    def populate_card_list(
        self, combo: QComboBox, show_ai_generated: bool = True, show_manual: bool = True
    ) -> None:
        """Populate a combo box with cards, optionally filtered by type."""
        combo.clear()

        # Wait for mw.col to be ready if not already
        if not mw.col:
            combo.addItem("Waiting for Anki to load...")
            return

        recent_cards = AnkiService.get_recent_cards(200)
        if not recent_cards:
            combo.addItem("No cards found - create a card first or use Browse")
            return

        categories = {"AI Generated": [], "Manual": []}

        for card_id in recent_cards:
            card = AnkiService.get_card_by_id(card_id)
            if not card:
                continue

            is_ai_generated = self.tag_manager.filter_ai_generated_cards_from_tags(
                card.tags
            )

            if is_ai_generated and show_ai_generated:
                categories["AI Generated"].append((card, card_id))
            elif not is_ai_generated and show_manual:
                categories["Manual"].append((card, card_id))

        # Populate with separators
        found_cards = False
        for category, cards_list in categories.items():
            if cards_list:
                found_cards = True
                combo.addItem(f"--- {category} ---")
                combo.model().item(combo.count() - 1).setEnabled(False)

                for card, card_id in cards_list:
                    display = f"[{card.deck_name}] {card.front[:60]}"
                    combo.addItem(display, card_id)

        if not found_cards:
            combo.addItem("No cards match filter - use Browse button")

    def get_selected_card(self, combo: QComboBox) -> CardInfo | None:
        """Resolve the selected card; skip separator rows with no stored card id."""
        idx = combo.currentIndex()
        for j in range(idx, -1, -1):
            cid = combo.itemData(j)
            if cid is not None:
                return AnkiService.get_card_by_id(int(cid))
        for j in range(combo.count()):
            cid = combo.itemData(j)
            if cid is not None:
                return AnkiService.get_card_by_id(int(cid))
        return None

    def ensure_combo_valid_card_row(self, combo: QComboBox) -> None:
        """If the user lands on a category separator, move to the nearest real card."""
        idx = combo.currentIndex()
        if combo.itemData(idx) is not None:
            return
        new_i: int | None = None
        for j in range(idx + 1, combo.count()):
            if combo.itemData(j) is not None:
                new_i = j
                break
        if new_i is None:
            for j in range(0, idx):
                if combo.itemData(j) is not None:
                    new_i = j
                    break
        if new_i is None:
            return
        combo.blockSignals(True)
        combo.setCurrentIndex(new_i)
        combo.blockSignals(False)
        combo.currentIndexChanged.emit(new_i)

    def browse_for_card(
        self, combo: QComboBox, parent_widget: QWidget | None = None
    ) -> bool:
        """
        Open Anki's browser to select a card.
        Returns True if a card was selected, False otherwise.
        """
        try:
            import aqt

            if parent_widget is not None:
                parent_widget.hide()
            QApplication.processEvents()

            browser = aqt.dialogs.open("Browser", mw)
            if getattr(browser.form, "searchEdit", None) is not None:
                browser.form.searchEdit.setFocus()
            browser.raise_()
            browser.activateWindow()
            QApplication.processEvents()

            loop = QEventLoop()
            last_cards: list[int] = []
            picked = False

            def finish(card_id: int) -> None:
                nonlocal picked
                self.selected_card_id = card_id
                card_info = AnkiService.get_card_by_id(card_id)
                if card_info is not None:
                    combo.blockSignals(True)
                    combo.clear()
                    display = f"[{card_info.deck_name}] {card_info.front[:60]}"
                    combo.addItem(display, card_id)
                    combo.setCurrentIndex(0)
                    combo.blockSignals(False)
                    combo.currentIndexChanged.emit(0)
                    picked = True

            def poll() -> None:
                try:
                    visible = browser.isVisible()
                except RuntimeError:
                    visible = False
                if visible:
                    try:
                        ids = browser.selected_cards()
                        if ids:
                            last_cards[:] = [int(cid) for cid in ids]
                    except RuntimeError:
                        pass
                    QTimer.singleShot(80, poll)
                    return
                if last_cards:
                    finish(last_cards[0])
                loop.quit()

            QTimer.singleShot(80, poll)
            loop.exec()
            return picked

        except Exception as e:
            print(f"[AI Flashcards] Error opening browser: {e}")
            traceback.print_exc()
            return False
        finally:
            if parent_widget is not None:
                parent_widget.show()
                parent_widget.raise_()
                parent_widget.activateWindow()
                QApplication.processEvents()


class EnhancedUI:
    """Enhanced UI with context awareness and better organization."""

    def __init__(self) -> None:
        self.state = UIState()
        self._debug_messages: list[str] = []
        self.tag_manager: TagManager | None = None
        self.hierarchy_manager: CardHierarchyManager | None = None
        self.card_selector: CardSelector | None = None
        self._build_menu()

    def _ensure_managers(self) -> None:
        """Initialize managers lazily."""
        if self.tag_manager is not None:
            return

        try:
            if getattr(mw, "col", None) and getattr(mw.col, "path", None):
                base = Path(mw.col.path).parent / "ai_flashcards_tags"
            else:
                base = Path.home() / ".ai_flashcards_tags"
        except Exception:
            base = Path.home() / ".ai_flashcards_tags"

        self.tag_manager = TagManager(base)
        self.hierarchy_manager = CardHierarchyManager(base)
        self.card_selector = CardSelector(self.tag_manager)

    def _log_debug(self, message: str) -> None:
        """Store and print debug info."""
        self._debug_messages.append(message)
        print(f"[AI Flashcards] {message}")

    def setup_context_menu_items(self) -> None:
        """Set up context menu items for cards."""
        try:
            # This is called during main window setup
            # Add a submenu in the Tools menu
            pass
        except Exception as e:
            print(f"[AI Flashcards] Error setting up context menu: {e}")

    def _build_menu(self) -> None:
        """Build the main menu."""
        try:
            # Check if menu already exists to avoid duplicates
            for existing_menu in mw.form.menubar.children():
                if (
                    hasattr(existing_menu, "title")
                    and existing_menu.title() == "AI Flashcards"
                ):
                    self.state.menu = existing_menu
                    return

            menu = QMenu("AI Flashcards", mw)
            mw.form.menubar.addMenu(menu)
            self.state.menu = menu

            # Main action
            action = QAction("Generate or Verify Cards", mw)
            qconnect(action.triggered, self.show_main_dialog)
            menu.addAction(action)
            self.state.menu_actions["main"] = action

            # Context-aware action
            action_context = QAction("Quick AI Tools (Context-Aware)", mw)
            qconnect(action_context.triggered, self.show_context_dialog)
            menu.addAction(action_context)
            self.state.menu_actions["context"] = action_context

            self._log_debug("Menu successfully registered")
        except Exception as e:
            self._log_debug(f"Error building menu: {e}")
            import traceback

            print(traceback.format_exc())

    def show_main_dialog(self) -> None:
        """Show the main AI flashcard dialog."""
        self._ensure_managers()

        if self.card_selector is None:
            showWarning("Failed to initialize card selector")
            return

        # Check if Anki is ready
        if not mw.col:
            showWarning("Anki is still loading. Please wait a moment and try again.")
            return

        dialog = QDialog(mw)
        dialog.setWindowTitle("AI Flashcard Manager")
        dialog.setMinimumSize(900, 700)

        layout = QVBoxLayout(dialog)

        # Card selection section with filtering
        card_layout = QHBoxLayout()
        card_layout.addWidget(QLabel("Select Card:"))

        card_combo = QComboBox()
        self.card_selector.populate_card_list(
            card_combo, show_ai_generated=True, show_manual=True
        )

        if card_combo.count() > 0:
            # Skip separators when setting initial index
            for i in range(card_combo.count()):
                if card_combo.itemData(i) is not None:
                    card_combo.setCurrentIndex(i)
                    break

        card_layout.addWidget(card_combo)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(
            lambda: self.card_selector.populate_card_list(card_combo)
        )
        card_layout.addWidget(refresh_button)

        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(
            lambda: self.card_selector.browse_for_card(card_combo, dialog)
        )
        card_layout.addWidget(browse_button)

        card_combo.currentIndexChanged.connect(
            lambda _i: self.card_selector.ensure_combo_valid_card_row(card_combo)
        )

        layout.addLayout(card_layout)

        # Tab widget for main functions
        tabs = QTabWidget()

        # Tab 1: Verify Card
        verify_tab = self._create_verify_tab(dialog, card_combo)
        tabs.addTab(verify_tab, "1. Verify Card")

        # Tab 2: Create Variants
        multi_type_tab = self._create_multi_type_tab(dialog, card_combo)
        tabs.addTab(multi_type_tab, "2. Create Variants")

        # Tab 3: Generate from Media
        generate_tab = self._create_generate_tab(dialog)
        tabs.addTab(generate_tab, "3. Create from Media")

        layout.addWidget(tabs)

        # Buttons
        buttons = QDialogButtonBox.StandardButton.Close
        button_box = QDialogButtonBox(buttons)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        self.state.dialogs["main"] = dialog
        dialog.exec()

    def show_context_dialog(self) -> None:
        """Show a context-aware quick dialog."""
        self._ensure_managers()

        if not mw.col:
            showWarning("Anki is still loading. Please wait a moment and try again.")
            return

        context_card = AnkiService.get_current_context_card()

        if not context_card:
            showWarning(
                "No card context available. Go to the main mode or review a card first, or use the Browse button to select one."
            )
            # Open main dialog as fallback
            self.show_main_dialog()
            return

        dialog = QDialog(mw)
        dialog.setWindowTitle("Quick AI Tools - Context Aware")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)

        # Show current context
        context_label = QLabel(
            f"Current Card: [{context_card.deck_name}] {context_card.front[:80]}"
        )
        layout.addWidget(context_label)

        # Quick buttons
        buttons_layout = QHBoxLayout()

        verify_button = QPushButton("Verify This Card")
        verify_button.setStyleSheet("background-color: #4CAF50; color: white;")
        verify_button.clicked.connect(lambda: self._quick_verify(context_card, dialog))
        buttons_layout.addWidget(verify_button)

        variants_button = QPushButton("Create Variants")
        variants_button.setStyleSheet("background-color: #2196F3; color: white;")
        variants_button.clicked.connect(
            lambda: self._quick_variants(context_card, dialog)
        )
        buttons_layout.addWidget(variants_button)

        layout.addLayout(buttons_layout)

        # Results area
        results = QTextEdit()
        results.setReadOnly(True)
        layout.addWidget(QLabel("Results:"))
        layout.addWidget(results)

        self.state.text_fields["context_results"] = results

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.exec()

    def _quick_verify(self, card: CardInfo, parent_dialog: QDialog) -> None:
        """Quickly verify the given card."""

        async def do_verify():
            try:
                config = mw.addonManager.getConfig("ai_flashcards") or {}
                provider = build_provider(config)
                service = CardVerificationService(provider)

                deck_context = AnkiService.get_deck_context(card.deck_name)
                result = await service.verify_card(card.front, card.back, deck_context)

                result_text = (
                    "✓ Card is valid!" if result.is_valid else "⚠ Issues found:"
                )
                if not result.is_valid:
                    for issue in result.issues:
                        result_text += f"\n• {issue}"

                if (
                    not result.is_valid
                    and result.suggested_improvements
                    and self.tag_manager is not None
                ):
                    added = self._apply_auto_single_info_improvements(
                        result.suggested_improvements, card
                    )
                    result_text += f"\n\nAdded {added} improved card(s); original tagged for review."
                self.state.text_fields["context_results"].setText(result_text)

                # Mark as verified if valid
                if result.is_valid and self.tag_manager is not None:
                    tags = self.tag_manager.get_verification_tags(is_verified=True)
                    AnkiService.add_tags_to_card(card.card_id, tags)

            except Exception as e:
                showWarning(f"Verification failed: {e}")

        asyncio.run(do_verify())

    def _quick_variants(self, card: CardInfo, parent_dialog: QDialog) -> None:
        """Create variants for the given card."""

        async def do_variants():
            try:
                config = mw.addonManager.getConfig("ai_flashcards") or {}
                provider = build_provider(config)
                service = CardVerificationService(provider)

                deck_context = AnkiService.get_deck_context(card.deck_name)
                result = await service.generate_multi_type_cards(
                    card.front, card.back, deck_context
                )

                self._show_multi_type_acceptance_dialog(
                    parent_dialog, result.cards, card
                )

            except Exception as e:
                showWarning(f"Generation failed: {e}")

        asyncio.run(do_variants())

    def _create_verify_tab(
        self, parent_dialog: QDialog, card_combo: QComboBox
    ) -> QWidget:
        """Create the verify card tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Verify the selected card:"))

        card_display = QTextEdit()
        card_display.setReadOnly(True)
        layout.addWidget(QLabel("Card Content:"))
        layout.addWidget(card_display)

        verify_button = QPushButton("Verify with AI")
        verify_button.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )

        async def verify_card():
            card = self.card_selector.get_selected_card(card_combo)
            if not card:
                showWarning("Please select a card first")
                return

            try:
                config = mw.addonManager.getConfig("ai_flashcards") or {}
                provider = build_provider(config)
                service = CardVerificationService(provider)

                deck_context = AnkiService.get_deck_context(card.deck_name)

                verify_button.setEnabled(False)
                verify_button.setText("Verifying...")

                result = await service.verify_card(card.front, card.back, deck_context)

                verify_button.setText("Verify with AI")
                verify_button.setEnabled(True)

                self._show_verification_results(parent_dialog, result, card)

            except Exception as exc:
                verify_button.setText("Verify with AI")
                verify_button.setEnabled(True)
                showWarning(f"Verification failed:\n{exc}\n\n{traceback.format_exc()}")

        verify_button.clicked.connect(lambda: asyncio.run(verify_card()))
        layout.addWidget(verify_button)

        results_display = QTextEdit()
        results_display.setReadOnly(True)
        layout.addWidget(QLabel("Results:"))
        layout.addWidget(results_display)

        self.state.text_fields["verify_results"] = results_display

        def update_card_display():
            card = self.card_selector.get_selected_card(card_combo)
            if card:
                card_display.setText(
                    f"Front:\n{card.front}\n\nBack:\n{card.back}\n\nDeck: {card.deck_name}\nTags: {', '.join(card.tags)}"
                )
            else:
                card_display.clear()

        card_combo.currentIndexChanged.connect(update_card_display)
        update_card_display()

        return widget

    def _create_multi_type_tab(
        self, parent_dialog: QDialog, card_combo: QComboBox
    ) -> QWidget:
        """Create the multi-type card generation tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Generate multiple card types from the selected card:"))

        card_display = QTextEdit()
        card_display.setReadOnly(True)
        layout.addWidget(QLabel("Original Card:"))
        layout.addWidget(card_display)

        generate_button = QPushButton("Generate Card Types")
        generate_button.setStyleSheet(
            "background-color: #2196F3; color: white; font-weight: bold;"
        )

        async def generate_variants():
            card = self.card_selector.get_selected_card(card_combo)
            if not card:
                showWarning("Please select a card first")
                return

            try:
                config = mw.addonManager.getConfig("ai_flashcards") or {}
                provider = build_provider(config)
                service = CardVerificationService(provider)

                deck_context = AnkiService.get_deck_context(card.deck_name)

                generate_button.setEnabled(False)
                generate_button.setText("Generating...")

                result = await service.generate_multi_type_cards(
                    card.front, card.back, deck_context
                )

                generate_button.setText("Generate Card Types")
                generate_button.setEnabled(True)

                self._show_multi_type_results(parent_dialog, result, card)

            except Exception as exc:
                generate_button.setText("Generate Card Types")
                generate_button.setEnabled(True)
                showWarning(f"Generation failed:\n{exc}\n\n{traceback.format_exc()}")

        generate_button.clicked.connect(lambda: asyncio.run(generate_variants()))
        layout.addWidget(generate_button)

        results_display = QTextEdit()
        results_display.setReadOnly(True)
        layout.addWidget(QLabel("Generated Variants:"))
        layout.addWidget(results_display)

        self.state.text_fields["multi_type_results"] = results_display

        def update_card_display():
            card = self.card_selector.get_selected_card(card_combo)
            if card:
                card_display.setText(
                    f"Front:\n{card.front}\n\nBack:\n{card.back}\n\nDeck: {card.deck_name}"
                )
            else:
                card_display.clear()

        card_combo.currentIndexChanged.connect(update_card_display)
        update_card_display()

        return widget

    def _create_generate_tab(self, parent_dialog: QDialog) -> QWidget:
        """Create the card generation from media tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Deck selection
        deck_layout = QHBoxLayout()
        deck_layout.addWidget(QLabel("Target Deck:"))

        deck_combo = QComboBox()
        all_decks = AnkiService.get_all_decks()
        for deck in all_decks:
            deck_combo.addItem(deck.name)

        deck_layout.addWidget(deck_combo)
        layout.addLayout(deck_layout)

        # Source type selection
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Source Type:"))

        source_combo = QComboBox()
        source_combo.addItems(
            ["Text Input", "PDF File", "Screenshot/Image", "Presentation Slide"]
        )
        source_layout.addWidget(source_combo)
        layout.addLayout(source_layout)

        # Number of cards
        num_layout = QHBoxLayout()
        num_layout.addWidget(QLabel("Cards to Generate:"))
        num_spin = QSpinBox()
        num_spin.setMinimum(1)
        num_spin.setMaximum(20)
        num_spin.setValue(5)
        num_layout.addWidget(num_spin)
        layout.addLayout(num_layout)

        # Content input
        content_display = QTextEdit()
        content_display.setPlaceholderText("Enter text content here...")
        layout.addWidget(QLabel("Content:"))
        layout.addWidget(content_display)

        # Debug output
        debug_output = QTextEdit()
        debug_output.setReadOnly(True)
        debug_output.setMaximumHeight(130)
        layout.addWidget(QLabel("Debug:"))
        layout.addWidget(debug_output)
        self.state.text_fields["generate_debug"] = debug_output

        # File button
        file_button = QPushButton("Select File")

        def select_file():
            dlg_opts = QFileDialog.Option.DontUseNativeDialog
            file_path, _ = QFileDialog.getOpenFileName(
                parent_dialog,
                "Select File",
                str(Path.home()),
                "Supported (*.pdf *.pptx *.png *.jpg *.jpeg *.bmp *.tiff *.txt *.md);;"
                "PDF (*.pdf);;PowerPoint (*.pptx);;"
                "Images (*.png *.jpg *.jpeg *.bmp *.tiff);;Text (*.txt *.md);;All files (*)",
                options=dlg_opts,
            )
            if not file_path:
                return

            try:
                import importlib

                p = Path(file_path)
                suffix = p.suffix.lower()

                if suffix in (".txt", ".md", ".markdown"):
                    content_display.setPlainText(
                        p.read_text(encoding="utf-8", errors="replace").strip()
                    )
                    source_combo.setCurrentIndex(0)
                    return

                if suffix == ".pdf":
                    try:
                        pdfplumber = importlib.import_module("pdfplumber")
                        text_pages = []
                        with pdfplumber.open(file_path) as pdf:
                            for page in pdf.pages:
                                txt = page.extract_text() or ""
                                text_pages.append(txt)
                        extracted = "\n\n".join(text_pages).strip()
                        content_display.setPlainText(
                            extracted or f"[PDF: no text extracted from {file_path}]"
                        )
                    except Exception:
                        try:
                            PdfReader = importlib.import_module("PyPDF2").PdfReader
                            reader = PdfReader(file_path)
                            texts = [pg.extract_text() or "" for pg in reader.pages]
                            extracted = "\n\n".join(texts).strip()
                            content_display.setPlainText(
                                extracted
                                or f"[PDF: no text extracted from {file_path}]"
                            )
                        except Exception:
                            content_display.setPlainText(
                                f"[PDF content from {file_path} - install pdfplumber or PyPDF2 for extraction]"
                            )
                    source_combo.setCurrentText("PDF File")

                elif suffix in (".png", ".jpg", ".jpeg", ".bmp", ".tiff"):
                    try:
                        Image = importlib.import_module("PIL.Image")
                        pytesseract = importlib.import_module("pytesseract")

                        img = Image.open(file_path)
                        extracted = pytesseract.image_to_string(img)
                        content_display.setPlainText(
                            extracted or f"[Image: no text found in {file_path}]"
                        )
                    except Exception:
                        content_display.setPlainText(
                            f"[Image text from {file_path} - install pillow+pytesseract for OCR]"
                        )
                    source_combo.setCurrentText("Screenshot/Image")

                elif suffix in (".pptx",):
                    try:
                        Presentation = importlib.import_module("pptx").Presentation
                        prs = Presentation(file_path)
                        texts = []
                        for slide in prs.slides:
                            for shape in slide.shapes:
                                if hasattr(shape, "text"):
                                    texts.append(shape.text)
                        content_display.setPlainText(
                            "\n\n".join(texts)
                            or f"[Slide: no text extracted from {file_path}]"
                        )
                    except Exception:
                        content_display.setPlainText(
                            f"[Presentation content from {file_path} - install python-pptx for extraction]"
                        )
                    source_combo.setCurrentText("Presentation Slide")

                else:
                    showWarning(
                        f"Unsupported file type ({suffix or 'unknown'}).\n\n"
                        "Use PDF, PPTX, images, or .txt/.md — or paste text manually."
                    )
            except Exception as e:
                showWarning(f"Error loading file: {e}")

        file_button.clicked.connect(select_file)
        layout.addWidget(file_button)

        # Generate button
        generate_button = QPushButton("Generate Cards")
        generate_button.setStyleSheet(
            "background-color: #FF9800; color: white; font-weight: bold;"
        )

        async def generate_new_cards():
            content = content_display.toPlainText().strip()
            if not content:
                showWarning("Please enter or select content")
                return

            deck_name = deck_combo.currentText()
            source_type = source_combo.currentText().lower()
            ai_source_type = self._source_type_for_upload(source_type)

            self._log_debug(
                f"Generate: deck='{deck_name}', source='{source_type}', ai_source='{ai_source_type}'"
            )
            debug_output.setPlainText("\n".join(self._debug_messages[-20:]))

            try:
                config = mw.addonManager.getConfig("ai_flashcards") or {}
                provider = build_provider(config)
                service = CardGenerationService(provider)

                deck_context = AnkiService.get_deck_context(deck_name)

                generate_button.setEnabled(False)
                generate_button.setText("Generating...")

                if ai_source_type != "text":
                    cards = await service.generate_from_image_text(
                        content, ai_source_type, deck_context, num_spin.value()
                    )
                else:
                    cards = await service.generate_from_text(
                        content, deck_context, num_spin.value()
                    )

                self._log_debug(f"AI returned {len(cards)} cards")

                if not cards:
                    self._log_debug("AI returned 0 cards; creating fallback cards")
                    cards = self._fallback_cards_from_text(content, num_spin.value())
                    self._log_debug(f"Fallback produced {len(cards)} cards")

                generate_button.setText("Generate Cards")
                generate_button.setEnabled(True)

                debug_output.setPlainText("\n".join(self._debug_messages[-20:]))

                self._show_generation_results(
                    parent_dialog, cards, deck_name, source_type
                )

            except Exception as exc:
                generate_button.setText("Generate Cards")
                generate_button.setEnabled(True)
                self._log_debug(f"Generation failed: {exc}")
                debug_output.setPlainText("\n".join(self._debug_messages[-20:]))
                showWarning(f"Generation failed:\n{exc}\n\n{traceback.format_exc()}")

        generate_button.clicked.connect(lambda: asyncio.run(generate_new_cards()))
        layout.addWidget(generate_button)

        return widget

    def _note_type_from_config(self, default: str = "Basic") -> str:
        try:
            cfg = mw.addonManager.getConfig("ai_flashcards") or {}
            name = str(cfg.get("note_type") or "").strip()
            return name if name else default
        except Exception:
            return default

    def _apply_auto_single_info_improvements(
        self, improvements: list[dict], original_card: CardInfo
    ) -> int:
        """Create notes from verification splits and tag the original for review."""
        if not improvements or self.tag_manager is None:
            return 0

        hm = self.hierarchy_manager
        if hm is not None and hm.get_group(original_card.card_id) is None:
            hm.create_group(
                original_card.card_id,
                group_name="AI single-info split",
                group_description="Auto-generated narrower cards",
            )

        added = 0
        for imp in improvements:
            front = str(imp.get("front") or "").strip()
            back = str(imp.get("back") or "").strip()
            if not front and not back:
                continue

            tags = self.tag_manager.get_complete_tags_for_generated_card(
                "text", is_verified=False, is_variant=True
            )
            tags.extend(["ai_improvement", "ai_single_info_split"])

            note_id = AnkiService.add_card(
                front=front or "(empty)",
                back=back or "(empty)",
                deck_name=original_card.deck_name,
                model_name=original_card.model_name,
                tags=tags,
            )
            if note_id:
                added += 1
                cid = AnkiService.get_first_card_id_for_note(note_id)
                if hm is not None and cid is not None:
                    hm.add_card_to_group(original_card.card_id, cid)

        AnkiService.add_tags_to_card(
            original_card.card_id,
            ["ai_needs_review", "ai_split_parent_note"],
        )
        maybe_reset = getattr(mw, "maybeReset", None)
        if callable(maybe_reset):
            maybe_reset()
        return added

    def _source_type_for_upload(self, source_type: str) -> str:
        """Normalize source type."""
        s = source_type.lower().strip()
        if s.startswith("text") and "input" in s:
            return "text"
        if "pdf" in s:
            return "pdf"
        if "slide" in s or "ppt" in s:
            return "slide"
        if "image" in s or "screenshot" in s:
            return "screenshot"
        return "text"

    def _fallback_cards_from_text(
        self, content: str, num_cards: int
    ) -> list[dict[str, str]]:
        """Create fallback cards from text."""
        import re

        chunks = [
            c.strip() for c in re.split(r"\n\s*\n+|(?<=[.!?])\s+", content) if c.strip()
        ]
        if not chunks:
            return []

        cards: list[dict[str, str]] = []
        for chunk in chunks[:num_cards]:
            sentence = chunk[:180]
            cards.append(
                {
                    "front": f"What is the main idea of: {sentence[:80]}?",
                    "back": sentence,
                    "tags": ["ai_fallback", "ai_from_text"],
                }
            )
        return cards

    def _show_verification_results(
        self, parent: QDialog, verification, card: CardInfo
    ) -> None:
        """Show card verification results."""
        result_text = ""

        if verification.is_valid:
            result_text += "✓ Card looks good!\n\n"
            result_text += "This card follows best practices.\n\n"
            if self.tag_manager is not None:
                tags = self.tag_manager.get_verification_tags(is_verified=True)
                AnkiService.add_tags_to_card(card.card_id, tags)
                result_text += "Card marked as 'ai_verified'\n"

        else:
            result_text += "⚠ Issues found:\n\n"
            for issue in verification.issues:
                result_text += f"• {issue}\n"

            imp = verification.suggested_improvements
            if imp and self.tag_manager is not None:
                n_added = self._apply_auto_single_info_improvements(imp, card)
                result_text += "\n\nSingle-information fix:\n"
                result_text += f"Automatically added {n_added} narrower card(s). "
                result_text += "The original note is tagged ai_needs_review / ai_split_parent_note.\n"
                for i, improvement in enumerate(imp, 1):
                    result_text += f"\n{i}. {improvement.get('type', 'Split')}:\n"
                    result_text += f"   Front: {improvement.get('front', '')}\n"
                    result_text += f"   Back: {improvement.get('back', '')}\n"
            elif not imp:
                result_text += "\n(No automatic split suggestions returned — try again or edit manually.)\n"

        self.state.text_fields["verify_results"].setText(result_text)

    def _show_multi_type_results(
        self, parent: QDialog, multi_cards: MultiTypeCards, original_card: CardInfo
    ) -> None:
        """Show multi-type card generation results."""
        result_text = f"Generated {len(multi_cards.cards)} different card types:\n\n"

        for i, card in enumerate(multi_cards.cards, 1):
            result_text += f"{i}. {card.get('type', 'Variant').title()}\n"
            result_text += f"   Front: {card.get('front', '')[:80]}...\n"
            result_text += f"   Back: {card.get('back', '')[:80]}...\n"
            if card.get("rationale"):
                result_text += f"   Why: {card.get('rationale')}\n"
            result_text += "\n"

        self.state.text_fields["multi_type_results"].setText(result_text)

        self._show_multi_type_acceptance_dialog(
            parent, multi_cards.cards, original_card
        )

    def _show_multi_type_acceptance_dialog(
        self, parent: QDialog, cards: list[dict], original_card: CardInfo
    ) -> None:
        """Show dialog to accept multi-type cards."""
        if not cards:
            return

        acceptance_dialog = QDialog(parent)
        acceptance_dialog.setWindowTitle("Add Card Variants")
        acceptance_dialog.setMinimumSize(700, 500)

        layout = QVBoxLayout(acceptance_dialog)
        layout.addWidget(QLabel("Select which variants to add:"))

        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        selected_flags: list[bool] = [True] * len(cards)

        for i, card in enumerate(cards, 1):
            frame_layout = QVBoxLayout()

            checkbox = QCheckBox(f"Add: {card.get('type', f'Variant {i}').title()}")
            checkbox.setChecked(True)

            def make_checker(idx):
                def on_toggle(state):
                    selected_flags[idx] = bool(state)

                return on_toggle

            checkbox.stateChanged.connect(make_checker(i - 1))
            frame_layout.addWidget(checkbox)

            frame_layout.addWidget(QLabel(f"Front: {card.get('front', '')[:100]}"))
            frame_layout.addWidget(QLabel(f"Back: {card.get('back', '')[:100]}"))

            scroll_layout.addLayout(frame_layout)
            scroll_layout.addWidget(QLabel("---"))

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        def add_selected():
            tags_base = cast(
                list[str],
                self.tag_manager.get_complete_tags_for_generated_card(
                    "text", is_verified=False
                ),
            )
            tags_base.append("ai_multi_type")

            added = 0
            for idx, flag in enumerate(selected_flags):
                if not flag:
                    continue
                card = cards[idx]
                tags = tags_base + [card.get("type", "variant")]
                AnkiService.add_card(
                    front=card.get("front", ""),
                    back=card.get("back", ""),
                    deck_name=original_card.deck_name,
                    model_name=original_card.model_name,
                    tags=tags,
                )
                added += 1

            showInfo(f"Added {added} card variants!")

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel  # type: ignore
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(add_selected)
        button_box.accepted.connect(acceptance_dialog.accept)
        button_box.rejected.connect(acceptance_dialog.reject)
        layout.addWidget(button_box)

        acceptance_dialog.exec()

    def _show_generation_results(
        self,
        parent: QDialog,
        cards: list[dict[str, str]],
        deck_name: str,
        source_type: str,
    ) -> None:
        """Show generated card preview and add to collection."""
        if not cards:
            showWarning("No cards were generated")
            return

        generation_dialog = QDialog(parent)
        generation_dialog.setWindowTitle("Generated Cards Preview")
        generation_dialog.setMinimumSize(800, 600)

        layout = QVBoxLayout(generation_dialog)
        layout.addWidget(
            QLabel(f"Generated {len(cards)} cards. Select which ones to add:")
        )

        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        cards_to_add: list[bool] = [True] * len(cards)

        for i, card in enumerate(cards, 1):
            frame_layout = QVBoxLayout()

            checkbox = QCheckBox(f"Add Card {i}")
            checkbox.setChecked(True)

            def make_checker(idx):
                def on_toggle(state):
                    cards_to_add[idx] = bool(state)

                return on_toggle

            checkbox.stateChanged.connect(make_checker(i - 1))
            frame_layout.addWidget(checkbox)

            frame_layout.addWidget(QLabel(f"Front:\n{card.get('front', '')[:100]}"))
            frame_layout.addWidget(QLabel(f"Back:\n{card.get('back', '')[:100]}"))

            tags = card.get("tags", [])
            frame_layout.addWidget(QLabel(f"Tags: {', '.join(tags)}"))

            scroll_layout.addLayout(frame_layout)
            scroll_layout.addWidget(QLabel("---"))

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        def add_all_selected():
            if not cards or not any(cards_to_add):
                showWarning("Select at least one card to add")
                return

            tags_base: list[str] = (
                self.tag_manager.get_complete_tags_for_generated_card(
                    source_type, is_verified=False
                )
            )

            added_count = 0
            for idx, flag in enumerate(cards_to_add):
                if not flag:
                    continue
                card = cards[idx]
                tags = tags_base + card.get("tags", [])
                note_id = AnkiService.add_card(
                    front=card.get("front", ""),
                    back=card.get("back", ""),
                    deck_name=deck_name,
                    model_name=self._note_type_from_config("Basic"),
                    tags=tags,
                )
                if note_id:
                    added_count += 1

            showInfo(f"Successfully added {added_count} cards!")
            generation_dialog.accept()

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel  # type: ignore
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(add_all_selected)
        button_box.rejected.connect(generation_dialog.reject)
        layout.addWidget(button_box)

        generation_dialog.exec()
