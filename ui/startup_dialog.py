import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QFileDialog
from PySide6.QtCore import Qt

class StartupDialog(QDialog):
    """A blocking dialog that forces the user to choose a project path before booting."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Studio P4 - Démarrage")
        self.setFixedSize(300, 200)
        self.result_data = None  # Will hold a tuple: ("NEW", None) or ("LOAD", folder_path)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("Bienvenue dans Studio P4")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title)
        
        btn_new = QPushButton("Nouveau Projet")
        btn_new.setMinimumHeight(40)
        btn_new.clicked.connect(self._create_new)
        layout.addWidget(btn_new)
        
        btn_load = QPushButton("Charger un Projet Existant")
        btn_load.setMinimumHeight(40)
        btn_load.clicked.connect(self._load_old)
        layout.addWidget(btn_load)

    def _create_new(self) -> None:
        self.result_data = ("NEW", None)
        self.accept() # Closes the dialog and returns True to the main loop

    def _load_old(self) -> None:
        base_dir = os.path.abspath("./Saves")
        os.makedirs(base_dir, exist_ok=True)
        
        folder_path = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier du projet", base_dir)
        
        if folder_path:
            self.result_data = ("LOAD", folder_path)
            self.accept()