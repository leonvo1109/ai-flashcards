import asyncio
import traceback

from dataclasses import dataclass, field

from PyQt6.QtWidgets import QTextEdit, QPushButton
from aqt import mw
from aqt.qt import QAction, QDialog, QDialogButtonBox, QLabel, QMenu, QVBoxLayout
from aqt.utils import qconnect, showInfo

from .llm.factory import build_provider
from .use_cases import SimpleRequest


@dataclass
class UIState:
    menu: QMenu | None = None
    menu_actions: dict[str, QAction] = field(default_factory=dict)
    dialogs: dict[str, QDialog] = field(default_factory=dict)
    text_fields: dict[str, QTextEdit] = field(default_factory=dict)


class UI:
    def __init__(self) -> None:
        self.state = UIState()
        self._build_menu()

    # ----- Setup -----

    def _build_menu(self) -> None:
        menu = QMenu("AI Flashcards", mw)
        mw.form.menubar.addMenu(menu)
        self.state.menu = menu

        action = QAction("Test prompting", mw)
        qconnect(action.triggered, self.show_prompt_test_dialog)
        menu.addAction(action)
        self.state.menu_actions["prompt_test"] = action

    # ----- Event handlers -----

    def show_prompt_test_dialog(self) -> None:

        dialog = QDialog(mw)
        dialog.setWindowTitle("Test prompting")

        layout = QVBoxLayout(dialog)

        text_input = QTextEdit()
        text_input.setPlaceholderText("enter a prompt")
        layout.addWidget(text_input)
        self.state.text_fields["prompt_test_input"] = text_input

        text_output = QTextEdit()
        text_output.setReadOnly(True)
        text_output.setPlaceholderText("response will be displayed here")
        layout.addWidget(text_output)
        self.state.text_fields["prompt_test_output"] = text_output

        generate_button = QPushButton("Generate response")
        generate_button.clicked.connect(lambda: QtAsyncio.run(self.generate_simple_response))
        layout.addWidget(generate_button)

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        self.state.dialogs["prompt_test"] = dialog

        dialog.exec()

    async def generate_simple_response(self):
        try:
            config = mw.addonManager.getConfig("ai_flashcards") or {}
            provider = build_provider(config)
            request = SimpleRequest(provider)
            async with asyncio.TaskGroup() as tg:
                task = tg.create_task(
                    request.ask(self.state.text_fields["prompt_test_input"].toPlainText())
                )
                #self.state.text_fields["prompt_test_output"].setText()

        except Exception as exc:
            showInfo(f"AI request failed:\n{exc}\n\n{traceback.format_exc()}")

