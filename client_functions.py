# Funciones pendientes de implementar en el cliente de chat
from PyQt5.QtWidgets import (
    QMessageBox, QAction, QApplication, QDialog, QVBoxLayout, QTabWidget, QWidget,
    QGridLayout, QPushButton, QSystemTrayIcon, QMenu
)
from PyQt5.QtGui import QIcon, QFont
import datetime

def clear_chat_history(self):
    """Limpia el historial de chat tras confirmación del usuario"""
    # Pedir confirmación al usuario
    reply = QMessageBox.question(
        self, 
        "Limpiar Historial", 
        "¿Está seguro que desea eliminar todo el historial de chat?\nEsta acción no se puede deshacer.",
        QMessageBox.Yes | QMessageBox.No, 
        QMessageBox.No
    )
    
    # Si el usuario confirma, limpiar el historial
    if reply == QMessageBox.Yes:
        self.chat_area.clear()
        self.append_system_message("El historial de chat ha sido eliminado")
        
        # Desplazarse al final del chat
        self.scroll_to_bottom()

def force_quit(self):
    """Fuerza el cierre de la aplicación después de desconectarse del servidor"""
    if self.client_thread and self.client_thread.isRunning():
        self.disconnect_from_server()
        
    # Guardar configuraciones antes de salir
    self.saveSettings()
    
    # Cerrar la aplicación
    QApplication.quit()

def update_time(self):
    """Actualiza la hora en la barra de estado"""
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    self.statusBar().showMessage(f"Cliente de Chat | {current_time}")

def show_emoji_selector(self):
    """Muestra un selector de emojis con más opciones"""
    # Categorías de emojis comunes
    emoji_categories = {
        "Caras": ["😊", "😂", "😍", "😎", "😢", "😡", "🤔", "😴", "🥳", "😷"],
        "Gestos": ["👍", "👌", "👏", "🙏", "🤝", "✌️", "👋", "🙌", "💪", "👊"],
        "Objetos": ["📱", "💻", "🔑", "💼", "📚", "🎮", "🎬", "📷", "🚗", "🏠"],
        "Símbolos": ["❤️", "⭐", "💯", "✅", "❌", "⚠️", "💤", "💭", "🔥", "✨"]
    }
    
    # Crear un diálogo para el selector
    dialog = QDialog(self)
    dialog.setWindowTitle("Seleccionar Emoji")
    dialog.setMinimumWidth(400)
    
    # Layout principal del diálogo
    layout = QVBoxLayout(dialog)
    
    # Pestañas para categorías
    tabs = QTabWidget()
    
    # Crear una pestaña para cada categoría
    for category, emoji_list in emoji_categories.items():
        tab = QWidget()
        grid = QGridLayout(tab)
        
        # Crear botones para cada emoji
        row, col = 0, 0
        for emoji_char in emoji_list:
            button = QPushButton(emoji_char)
            button.setMinimumSize(40, 40)
            button.setFont(QFont("Segoe UI Emoji", 14))
            button.clicked.connect(lambda checked, e=emoji_char: self.insert_emoji(e) or dialog.accept())
            
            grid.addWidget(button, row, col)
            
            # Avanzar a la siguiente posición
            col += 1
            if col >= 5:  # 5 emojis por fila
                col = 0
                row += 1
        
        tabs.addTab(tab, category)
    
    layout.addWidget(tabs)
    
    # Botón para cerrar
    close_button = QPushButton("Cerrar")
    close_button.clicked.connect(dialog.reject)
    layout.addWidget(close_button)
    
    # Mostrar el diálogo
    dialog.exec_()

def setupTrayIcon(self):
    """Configura el icono de la bandeja del sistema"""
    # Crear icono en la bandeja
    self.tray_icon = QSystemTrayIcon(QIcon('chat.png'), self)
    
    # Crear menú contextual
    tray_menu = QMenu()
    
    # Acción para mostrar/ocultar la ventana
    show_action = QAction("Mostrar/Ocultar", self)
    show_action.triggered.connect(self.toggleVisibility)
    tray_menu.addAction(show_action)
    
    # Acción para salir
    quit_action = QAction("Salir", self)
    quit_action.triggered.connect(self.force_quit)
    tray_menu.addAction(quit_action)
    
    # Asignar menú al icono
    self.tray_icon.setContextMenu(tray_menu)
    
    # Conectar señal de activación (doble clic)
    self.tray_icon.activated.connect(self.tray_icon_activated)
    
    # Mostrar icono en la bandeja
    self.tray_icon.show()

def tray_icon_activated(self, reason):
    """Maneja la activación del icono en la bandeja del sistema"""
    if reason == QSystemTrayIcon.DoubleClick:
        self.toggleVisibility()

def toggleVisibility(self):
    """Alterna la visibilidad de la ventana principal"""
    if self.isVisible():
        self.hide()
    else:
        self.show()
        self.activateWindow()  # Traer al frente
