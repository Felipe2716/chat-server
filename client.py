import socket
import sys
import threading
import datetime
import emoji
import re
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTextEdit, QPushButton, QVBoxLayout, 
                            QWidget, QLabel, QLineEdit, QHBoxLayout, QMessageBox, 
                            QSplitter, QToolButton, QMenu, QAction, QColorDialog, QFontDialog,
                            QTabWidget, QGroupBox, QGridLayout, QComboBox, QCheckBox,
                            QSystemTrayIcon, QFileDialog, QFrame, QInputDialog)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSize, QTimer, QSettings
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QColor, QPalette, QPixmap, QTextCharFormat

class ClientThread(QThread):
    update_signal = pyqtSignal(str, str)  # mensaje, tipo (normal, sistema, error)
    connection_signal = pyqtSignal(bool)  # estado de conexión
    
    def __init__(self, host, port, username):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.client_socket = None
        self.running = False
    
    def run(self):
        """Ejecuta el cliente en un hilo separado"""
        self.running = True
        
        try:
            # Crear socket y conectar
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            self.connection_signal.emit(True)
            
            while self.running:
                try:
                    # Recibir datos del servidor
                    message = self.client_socket.recv(1024).decode('utf-8')
                    
                    if message:
                        if message == "ALIAS":
                            # Enviar nombre de usuario
                            self.client_socket.send(self.username.encode('utf-8'))
                        elif message.startswith("SERVIDOR:"):
                            # Mensaje del sistema
                            self.update_signal.emit(message, "sistema")
                        else:
                            # Mensaje de otro usuario
                            self.update_signal.emit(message, "normal")
                except Exception as e:
                    if self.running:
                        self.update_signal.emit(f"Error de conexión: {str(e)}", "error")
                        self.connection_signal.emit(False)
                        self.running = False
        except Exception as e:
            self.update_signal.emit(f"Error al conectar con el servidor: {str(e)}", "error")
            self.connection_signal.emit(False)
        
        # Cerrar conexión al terminar
        if self.client_socket:
            self.client_socket.close()
    
    def send_message(self, message):
        """Envía un mensaje al servidor"""
        if self.running and self.client_socket:
            try:
                self.client_socket.send(message.encode('utf-8'))
                if message.lower() == "salir":
                    self.stop()
                return True
            except:
                self.update_signal.emit("Error al enviar el mensaje", "error")
                return False
        return False
    
    def stop(self):
        """Detiene el cliente"""
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        self.connection_signal.emit(False)
        # Esperar a que el hilo termine
        self.wait()

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.client_thread = None
        self.text_color = QColor(0, 0, 0)  # Color negro por defecto
        self.text_font = QFont("Arial", 10)
        self.is_dark_mode = True  # Por defecto, tema oscuro
        self.settings = QSettings("ChatApp", "Client")
        self.loadSettings()
        self.initUI()
        # self.setupTrayIcon()  # Eliminado porque el método no está implementado
        self.applyTheme() 
        
    def initUI(self):
        """Configura la interfaz de usuario"""
        self.setWindowTitle("Cliente de Chat v2.0")
        self.setGeometry(300, 300, 900, 700)
        
        # Icono de la aplicación
        self.setWindowIcon(QIcon('chat.png'))
        
        # Widget central y layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal con tabs
        main_layout = QVBoxLayout(central_widget)
        
        # Encabezado
        header_layout = QHBoxLayout()
        
        # Logo (si existe)
        try:
            logo_label = QLabel()
            logo_pixmap = QPixmap('chat_logo.png').scaledToHeight(50, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
            header_layout.addWidget(logo_label)
        except:
            # Si no hay logo, añadir un espaciador
            header_layout.addSpacing(20)
        
        # Título
        title_label = QLabel("CHAT EN TIEMPO REAL")
        title_label.setFont(QFont("Montserrat", 20, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label, 1)
        
        # Panel de estado
        status_box = QGroupBox("Estado")
        status_layout = QVBoxLayout(status_box)
        
        self.status_label = QLabel("Desconectado")
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.status_label.setStyleSheet("color: #CF6679;")  # Rojo para desconectado
        self.status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_label)
        
        header_layout.addWidget(status_box)
        
        main_layout.addLayout(header_layout)
        
        # Pestañas
        tab_widget = QTabWidget()
        
        # Tab Principal
        main_tab = QWidget()
        main_tab_layout = QVBoxLayout(main_tab)
        
        # Grupo de configuración
        config_group = QGroupBox("Conexión al Servidor")
        config_layout = QGridLayout(config_group)
        
        config_layout.addWidget(QLabel("Dirección IP:"), 0, 0)
        self.host_input = QLineEdit()
        self.host_input.setText(self.host)
        config_layout.addWidget(self.host_input, 0, 1)
        
        config_layout.addWidget(QLabel("Puerto:"), 0, 2)
        self.port_input = QLineEdit()
        self.port_input.setText(self.port)
        config_layout.addWidget(self.port_input, 0, 3)
        
        config_layout.addWidget(QLabel("Nombre:"), 1, 0)
        self.username_input = QLineEdit()
        self.username_input.setText(self.username)
        config_layout.addWidget(self.username_input, 1, 1)
        
        # Botones de control
        self.connect_button = QPushButton("CONECTAR")
        self.connect_button.setIcon(QIcon('connect.png'))
        self.connect_button.setMinimumHeight(40)
        self.connect_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
            QPushButton:disabled {
                background-color: #A5D6A7;
                color: #E0E0E0;
            }
        """)
        self.connect_button.clicked.connect(self.connect_to_server)
        config_layout.addWidget(self.connect_button, 1, 2)
        
        self.disconnect_button = QPushButton("DESCONECTAR")
        self.disconnect_button.setIcon(QIcon('disconnect.png'))
        self.disconnect_button.setMinimumHeight(40)
        self.disconnect_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.disconnect_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #EF5350;
            }
            QPushButton:disabled {
                background-color: #FFCDD2;
                color: #E0E0E0;
            }
        """)
        self.disconnect_button.clicked.connect(self.disconnect_from_server)
        self.disconnect_button.setEnabled(False)
        config_layout.addWidget(self.disconnect_button, 1, 3)
        
        main_tab_layout.addWidget(config_group)
        
        # Grupo de chat
        chat_group = QGroupBox("Conversación")
        chat_layout = QVBoxLayout(chat_group)
        
        # Área de chat
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setFont(QFont("Arial", 10))
        chat_layout.addWidget(self.chat_area)
        
        main_tab_layout.addWidget(chat_group, 1)  # Dar más espacio al chat
        
        # Área para escribir mensaje
        message_group = QGroupBox("Enviar Mensaje")
        message_layout = QHBoxLayout(message_group)
        
        # Botones de formato
        format_button = QToolButton()
        format_button.setIcon(QIcon('format.png'))
        format_button.setIconSize(QSize(20, 20))
        format_button.setToolTip("Formato de texto")
        
        # Menú de formato
        format_menu = QMenu(self)
        
        # Acción para cambiar color de texto
        color_action = QAction(QIcon('color.png'), "Color de texto", self)
        color_action.triggered.connect(self.change_text_color)
        format_menu.addAction(color_action)
        
        # Acción para cambiar fuente
        font_action = QAction(QIcon('font.png'), "Cambiar fuente", self)
        font_action.triggered.connect(self.change_text_font)
        format_menu.addAction(font_action)
        
        format_button.setMenu(format_menu)
        format_button.setPopupMode(QToolButton.InstantPopup)
        message_layout.addWidget(format_button)
        
        # Botones de emojis
        emoji_button = QToolButton()
        emoji_button.setIcon(QIcon('emoji.png'))
        emoji_button.setIconSize(QSize(20, 20))
        emoji_button.setToolTip("Insertar emoji")
        emoji_button.clicked.connect(self.show_emoji_selector)
        message_layout.addWidget(emoji_button)
        
        # Campo de texto para mensaje
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(70)
        self.message_input.setPlaceholderText("Escribe tu mensaje aquí...")
        self.message_input.setFont(self.text_font)
        self.message_input.setTextColor(self.text_color)
        message_layout.addWidget(self.message_input)
        
        # Botón de enviar
        self.send_button = QPushButton("ENVIAR")
        self.send_button.setIcon(QIcon('send.png'))
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setEnabled(False)
        self.send_button.setMinimumHeight(40)
        self.send_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #42A5F5;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        message_layout.addWidget(self.send_button)
        
        # Botón para enviar archivos
        file_button = QToolButton()
        file_button.setIcon(QIcon('file.png'))
        file_button.setIconSize(QSize(20, 20))
        file_button.setToolTip("Enviar archivo")
        file_button.clicked.connect(self.send_file)
        message_layout.insertWidget(2, file_button)  # Lo coloca antes del campo de texto
        
        main_tab_layout.addWidget(message_group)
        
        # Añadir la pestaña principal
        tab_widget.addTab(main_tab, "Chat")
        
        # Tab de Configuración
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        
        # Grupo de opciones
        options_group = QGroupBox("Opciones")
        options_layout = QVBoxLayout(options_group)
        
        # Tema
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Tema:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Oscuro", "Claro"])
        if not self.is_dark_mode:
            self.theme_combo.setCurrentIndex(1)
        self.theme_combo.currentIndexChanged.connect(self.change_theme)
        theme_layout.addWidget(self.theme_combo)
        options_layout.addLayout(theme_layout)
        
        # Opciones adicionales
        self.auto_emoji_checkbox = QCheckBox("Convertir emoticones automáticamente (ej: ':)' → 😊)")
        self.auto_emoji_checkbox.setChecked(self.auto_emoji)
        options_layout.addWidget(self.auto_emoji_checkbox)
        
        self.tray_checkbox = QCheckBox("Minimizar a bandeja del sistema al cerrar")
        self.tray_checkbox.setChecked(self.minimize_to_tray)
        options_layout.addWidget(self.tray_checkbox)
        
        settings_layout.addWidget(options_group)
        
        # Añadir botones para exportar e importar historial
        buttons_layout = QHBoxLayout()
        
        export_button = QPushButton("Exportar historial de chat")
        export_button.clicked.connect(self.export_chat_history)
        buttons_layout.addWidget(export_button)
        
        clear_button = QPushButton("Limpiar historial")
        clear_button.clicked.connect(self.clear_chat_history)
        buttons_layout.addWidget(clear_button)
        
        self.add_search_button(buttons_layout)
        
        settings_layout.addLayout(buttons_layout)
        settings_layout.addStretch()
        
        # Añadir la pestaña de configuración
        tab_widget.addTab(settings_tab, "Configuración")
        
        main_layout.addWidget(tab_widget)
        
        # Barra de estado
        self.statusBar().showMessage("Cliente de Chat listo")
        
        # Información del desarrollador
        dev_layout = QHBoxLayout()
        dev_info = QLabel("© " + str(datetime.datetime.now().year) + " - Cliente de Chat con PyQt5")
        dev_info.setAlignment(Qt.AlignRight)
        dev_layout.addWidget(dev_info)
        
        # Botón para cambiar tema rápidamente
        self.theme_button = QPushButton()
        self.theme_button.setIcon(QIcon('theme.png'))
        self.theme_button.setToolTip("Cambiar tema")
        self.theme_button.clicked.connect(self.toggle_theme)
        self.theme_button.setFixedSize(30, 30)
        dev_layout.addWidget(self.theme_button)
        
        main_layout.addLayout(dev_layout)
        
        # Temporizador para actualizar la hora
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # Actualizar cada segundo
    
    def loadSettings(self):
        """Carga configuraciones guardadas"""
        self.is_dark_mode = self.settings.value("darkMode", True, type=bool)
        self.host = self.settings.value("host", "172.20.10.12", type=str)
        self.port = self.settings.value("port", "12345", type=str)
        self.username = self.settings.value("username", "", type=str)
        self.minimize_to_tray = self.settings.value("minimizeToTray", False, type=bool)
        self.auto_emoji = self.settings.value("autoEmoji", True, type=bool)
        
        # Cargar fuente y color
        font_family = self.settings.value("fontFamily", "Arial", type=str)
        font_size = self.settings.value("fontSize", 10, type=int)
        self.text_font = QFont(font_family, font_size)
        
        color_name = self.settings.value("textColor", "#000000", type=str)
        self.text_color = QColor(color_name)
    
    def saveSettings(self):
        """Guarda configuraciones"""
        self.settings.setValue("darkMode", self.is_dark_mode)
        self.settings.setValue("host", self.host_input.text())
        self.settings.setValue("port", self.port_input.text())
        self.settings.setValue("username", self.username_input.text())
        self.settings.setValue("minimizeToTray", self.tray_checkbox.isChecked() if hasattr(self, 'tray_checkbox') else False)
        self.settings.setValue("autoEmoji", self.auto_emoji_checkbox.isChecked() if hasattr(self, 'auto_emoji_checkbox') else True)
        
        # Guardar fuente y color
        self.settings.setValue("fontFamily", self.text_font.family())
        self.settings.setValue("fontSize", self.text_font.pointSize())
        self.settings.setValue("textColor", self.text_color.name())
    
    def connect_to_server(self):
        """Conecta al servidor"""
        if not self.client_thread or not self.client_thread.isRunning():
            try:
                host = self.host_input.text()
                port = int(self.port_input.text())
                username = self.username_input.text()
                
                # Validar entradas
                if not host or not username:
                    QMessageBox.warning(self, "Advertencia", "Por favor, complete todos los campos.")
                    return
                
                # Iniciar hilo de cliente
                self.client_thread = ClientThread(host, port, username)
                self.client_thread.update_signal.connect(self.update_chat)
                self.client_thread.connection_signal.connect(self.update_connection_status)
                self.client_thread.start()
                
                # Mostrar mensaje de conexión
                self.append_system_message("Conectando al servidor...")
                
            except ValueError:
                QMessageBox.warning(self, "Error", "El puerto debe ser un número entero.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al conectar: {str(e)}")
    
    def disconnect_from_server(self):
        """Desconecta del servidor"""
        if self.client_thread and self.client_thread.isRunning():
            # Enviar mensaje de salida
            self.client_thread.send_message("salir")
            self.client_thread.stop()
            
            # Actualizar interfaz
            self.update_connection_status(False)
            self.append_system_message("Desconectado del servidor")
    
    def attempt_reconnect(self):
        """Intenta reconectar automáticamente si la conexión se pierde"""
        if not self.client_thread or not self.client_thread.isRunning():
            self.append_system_message("Intentando reconectar en 3 segundos...")
            QTimer.singleShot(3000, self.connect_to_server)

    def update_connection_status(self, connected):
        """Actualiza el estado de conexión en la interfaz"""
        if connected:
            self.status_label.setText("Conectado")
            self.status_label.setStyleSheet("color: green;")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.send_button.setEnabled(True)
            self.host_input.setEnabled(False)
            self.port_input.setEnabled(False)
            self.username_input.setEnabled(False)
        else:
            self.status_label.setText("Desconectado")
            self.status_label.setStyleSheet("color: red;")
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.send_button.setEnabled(False)
            self.host_input.setEnabled(True)
            self.port_input.setEnabled(True)
            self.username_input.setEnabled(True)
            self.attempt_reconnect()
    
    def show_notification(self, title, message):
        """Muestra una notificación de escritorio si la ventana no está activa"""
        if not self.isActiveWindow():
            try:
                from PyQt5.QtWidgets import QSystemTrayIcon
                tray = QSystemTrayIcon(self)
                tray.setIcon(QIcon('chat.png'))
                tray.show()
                tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)
            except Exception:
                pass

    def update_chat(self, message, message_type):
        """Actualiza el área de chat con nuevos mensajes y muestra notificación si es necesario"""
        if message_type == "normal":
            self.append_normal_message(message)
            # Notificación solo si la ventana no está activa
            self.show_notification("Nuevo mensaje", message)
        elif message_type == "sistema":
            self.append_system_message(message)
        elif message_type == "error":
            self.append_error_message(message)
    
    def preview_links_in_chat(self, message):
        """Detecta enlaces en el mensaje y muestra una vista previa básica"""
        url_pattern = r'(https?://\S+)'  # Simple regex para URLs
        urls = re.findall(url_pattern, message)
        for url in urls:
            # Solo muestra el enlace como clickeable (mejoras: usar requests y extraer título)
            self.chat_area.append(f"<a href='{url}' style='color:#1976D2;'>{url}</a>")

    def append_normal_message(self, message):
        """Añade un mensaje normal al chat"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Separar el nombre del usuario del mensaje
        parts = message.split(':', 1)
        if len(parts) == 2:
            username = parts[0]
            content = parts[1]
            
            # Formato de hora
            self.chat_area.append(f"<span style='color: #888888; font-size: 8pt;'>[{current_time}]</span>")
            
            # Formato de usuario y mensaje
            self.chat_area.append(f"<b>{username}:</b> {emoji.emojize(content)}")
            self.preview_links_in_chat(content)
        else:
            # Si no tiene el formato esperado, mostrar tal cual
            self.chat_area.append(f"<span style='color: #888888; font-size: 8pt;'>[{current_time}]</span> {message}")
            self.preview_links_in_chat(message)
        
        # Auto-scroll al final
        self.scroll_to_bottom()
    
    def append_system_message(self, message):
        """Añade un mensaje del sistema al chat"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Reemplazar "SERVIDOR: " si existe
        if message.startswith("SERVIDOR: "):
            message = message[10:]
        
        self.chat_area.append(f"<span style='color: #888888; font-size: 8pt;'>[{current_time}]</span>")
        self.chat_area.append(f"<span style='color: blue;'><i>Sistema: {emoji.emojize(message)}</i></span>")
        
        # Auto-scroll al final
        self.scroll_to_bottom()
    
    def append_error_message(self, message):
        """Añade un mensaje de error al chat"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        self.chat_area.append(f"<span style='color: #888888; font-size: 8pt;'>[{current_time}]</span>")
        self.chat_area.append(f"<span style='color: red;'><b>Error:</b> {message}</span>")
        
        # Auto-scroll al final
        self.scroll_to_bottom()
    
    def scroll_to_bottom(self):
        """Desplaza el chat al final"""
        cursor = self.chat_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_area.setTextCursor(cursor)
    
    def send_message(self):
        """Envía un mensaje al servidor o ejecuta comando"""
        if self.client_thread and self.client_thread.isRunning():
            message = self.message_input.toPlainText().strip()
            if message:
                if not self.handle_command(message):
                    success = self.client_thread.send_message(message)
                    if success:
                        self.message_input.clear()
                else:
                    self.message_input.clear()
    
    def send_private_message(self, recipient, message):
        """Envía un mensaje privado (DM) a otro usuario (solo formato de mensaje)"""
        if self.client_thread and self.client_thread.isRunning():
            self.client_thread.send_message(f"/dm {recipient} {message}")
            self.append_system_message(f"(Privado a {recipient}): {message}")

    def handle_command(self, message):
        """Procesa comandos de chat como /dm, /me, /clear, /help"""
        if message.startswith("/dm "):
            try:
                _, recipient, msg = message.split(' ', 2)
                self.send_private_message(recipient, msg)
            except Exception:
                self.append_error_message("Uso correcto: /dm usuario mensaje")
            return True
        elif message.startswith("/me "):
            action = message[4:]
            self.client_thread.send_message(f"* {self.username_input.text()} {action}")
            return True
        elif message.startswith("/clear"):
            self.clear_chat_history()
            return True
        elif message.startswith("/help"):
            help_text = (
                "Comandos disponibles:\n"
                "/dm usuario mensaje - Mensaje privado\n"
                "/me acción - Mensaje de acción\n"
                "/clear - Limpiar chat\n"
                "/help - Mostrar ayuda"
            )
            QMessageBox.information(self, "Ayuda de comandos", help_text)
            return True
        return False

    def send_file(self):
        """Permite enviar un archivo al servidor (solo envía la ruta como demo)"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo para enviar")
        if file_path:
            # En una implementación real, aquí se enviaría el archivo por el socket
            # Por ahora, solo se envía el nombre del archivo como mensaje
            if self.client_thread and self.client_thread.isRunning():
                filename = os.path.basename(file_path)
                self.client_thread.send_message(f"[Archivo enviado]: {filename}")
                self.append_system_message(f"Has enviado el archivo: {filename}")

    def change_text_color(self):
        """Cambia el color del texto para los mensajes"""
        color = QColorDialog.getColor(self.text_color, self)
        if color.isValid():
            self.text_color = color
            self.message_input.setTextColor(color)
    
    def change_text_font(self):
        """Cambia la fuente del texto para los mensajes"""
        font, ok = QFontDialog.getFont(self.text_font, self)
        if ok:
            self.text_font = font
            self.message_input.setFont(font)
    
    def insert_emoji(self, emoji_char):
        """Inserta un emoji en el campo de mensaje"""
        self.message_input.insertPlainText(emoji_char)
    
    def closeEvent(self, event):
        """Maneja el evento de cierre de la ventana"""
        if self.client_thread and self.client_thread.isRunning():
            reply = QMessageBox.question(self, 'Confirmar salida', 
                '¿Está seguro que desea salir del chat?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.disconnect_from_server()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
    
    def applyTheme(self):
        """Aplica el tema claro u oscuro a toda la aplicación"""
        palette = QPalette()
        
        if self.is_dark_mode:
            # Tema oscuro
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
            palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
            palette.setColor(QPalette.Text, QColor(255, 255, 255))
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
            
            # Estilo para QGroupBox y otros widgets
            self.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #6c6c6c;
                    border-radius: 5px;
                    margin-top: 10px;
                    font-weight: bold;
                    background-color: #444444;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top center;
                    padding: 0 5px;
                    color: #ffffff;
                }
                QTextEdit, QLineEdit, QComboBox {
                    border: 1px solid #6c6c6c;
                    border-radius: 3px;
                    padding: 2px;
                    background-color: #333333;
                    color: #ffffff;
                }
                QTabWidget::pane {
                    border: 1px solid #6c6c6c;
                    border-radius: 3px;
                }
                QTabBar::tab {
                    background-color: #444444;
                    color: #ffffff;
                    padding: 5px 15px;
                    border-top-left-radius: 3px;
                    border-top-right-radius: 3px;
                }
                QTabBar::tab:selected {
                    background-color: #666666;
                }
                QCheckBox {
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                QPushButton {
                    border-radius: 3px;
                    padding: 5px;
                }
            """)
        else:
            # Tema claro
            palette.setColor(QPalette.Window, QColor(240, 240, 240))
            palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.AlternateBase, QColor(233, 233, 233))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
            palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.Text, QColor(0, 0, 0))
            palette.setColor(QPalette.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Link, QColor(0, 0, 255))
            palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
            palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
            
            # Estilo para QGroupBox y otros widgets
            self.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #cccccc;
                    border-radius: 5px;
                    margin-top: 10px;
                    font-weight: bold;
                    background-color: #f0f0f0;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top center;
                    padding: 0 5px;
                    color: #000000;
                }
                QTextEdit, QLineEdit, QComboBox {
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                    padding: 2px;
                    background-color: #ffffff;
                    color: #000000;
                }
                QTabWidget::pane {
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                }
                QTabBar::tab {
                    background-color: #e0e0e0;
                    color: #000000;
                    padding: 5px 15px;
                    border-top-left-radius: 3px;
                    border-top-right-radius: 3px;
                }
                QTabBar::tab:selected {
                    background-color: #f5f5f5;
                }
                QCheckBox {
                    color: #000000;
                }
                QLabel {
                    color: #000000;
                }
                QPushButton {
                    border-radius: 3px;
                    padding: 5px;
                }
            """)
            
        # Aplicar paleta de colores
        QApplication.setPalette(palette)
        
    def toggle_theme(self):
        """Cambia entre tema claro y oscuro"""
        self.is_dark_mode = not self.is_dark_mode
        
        # Actualizar combobox si existe
        if hasattr(self, 'theme_combo'):
            self.theme_combo.setCurrentIndex(0 if self.is_dark_mode else 1)
        
        # Aplicar tema
        self.applyTheme()
        
        # Guardar preferencia
        self.saveSettings()
    
    def change_theme(self, index):
        """Cambiar tema desde el combobox"""
        self.is_dark_mode = (index == 0)  # 0 = Oscuro, 1 = Claro
        self.applyTheme()
        self.saveSettings()
    
    def export_chat_history(self):
        """Exporta el historial de chat a un archivo de texto"""
        # Obtener la ruta del archivo mediante un diálogo
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Exportar Historial de Chat",
            os.path.expanduser("~/historial_chat.txt"),
            "Archivos de texto (*.txt);;Archivos HTML (*.html);;Todos los archivos (*.*)"
        )
        
        if not file_path:
            return  # El usuario canceló el diálogo
            
        try:
            # Determinar el formato de exportación basado en la extensión
            is_html = file_path.lower().endswith('.html')
            
            with open(file_path, 'w', encoding='utf-8') as file:
                if is_html:
                    # Exportar en formato HTML
                    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Historial de Chat</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .timestamp { color: #888888; font-size: 80%; }
        .system { color: blue; font-style: italic; }
        .error { color: red; font-weight: bold; }
        .message { margin-bottom: 10px; }
    </style>
</head>
<body>
    <h1>Historial de Chat</h1>
    <p>Exportado: {}</p>
    <div class="chat-history">
        {}
    </div>
</body>
</html>"""
                    
                    # Obtener el contenido HTML del chat
                    chat_content = self.chat_area.toHtml()
                    # Extraer solo la parte relevante
                    chat_html = chat_content
                    
                    # Formatear y escribir el HTML
                    export_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    file.write(html_content.format(export_time, chat_html))
                    
                else:
                    # Exportar como texto plano
                    file.write("=== HISTORIAL DE CHAT ===\n")
                    file.write(f"Exportado: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
                    
                    # Obtener el texto plano del chat
                    chat_text = self.chat_area.toPlainText()
                    file.write(chat_text)
                
            # Mostrar mensaje de éxito
            QMessageBox.information(
                self, 
                "Exportación Completada", 
                f"El historial de chat se ha exportado correctamente a:\n{file_path}"
            )
            
        except Exception as e:
            # Mostrar mensaje de error
            QMessageBox.critical(
                self, 
                "Error de Exportación", 
                f"No se pudo exportar el historial de chat: {str(e)}"
            )
    
    def clear_chat_history(self):
        """Limpia el área de chat"""
        self.chat_area.clear()
    
    def search_chat_history(self, query):
        """Busca mensajes en el historial de chat"""
        results = []
        for line in self.chat_area.toPlainText().splitlines():
            if query.lower() in line.lower():
                results.append(line)
        if results:
            QMessageBox.information(self, "Resultados de búsqueda", '\n'.join(results))
        else:
            QMessageBox.information(self, "Resultados de búsqueda", "No se encontraron coincidencias.")

    def add_search_button(self, layout):
        """Agrega un botón de búsqueda de historial al layout de configuración"""
        search_button = QPushButton("Buscar en historial")
        search_button.clicked.connect(lambda: self.search_chat_history(QInputDialog.getText(self, "Buscar en historial", "Palabra o frase a buscar:")[0]))
        layout.addWidget(search_button)

    def update_time(self):
        """Actualiza la barra de estado con la hora actual"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.statusBar().showMessage(f"Cliente de Chat listo - {current_time}")

    def show_emoji_selector(self):
        """Muestra un selector de emojis con más opciones"""
        from client_functions import show_emoji_selector
        show_emoji_selector(self)

    def typing_indicator(self):
        """Envía un indicador de escritura al servidor (solo local demo)"""
        if self.client_thread and self.client_thread.isRunning():
            # En una implementación real, se enviaría un mensaje especial al servidor
            self.statusBar().showMessage("Escribiendo...")
            QTimer.singleShot(1500, self.update_time)
        
    def custom_theme_dialog(self):
        """Permite al usuario personalizar el color de fondo y texto del chat"""
        bg_color = QColorDialog.getColor(self.palette().color(QPalette.Base), self, "Color de fondo del chat")
        if not bg_color.isValid():
            return
        text_color = QColorDialog.getColor(self.text_color, self, "Color de texto del chat")
        if not text_color.isValid():
            return
        self.chat_area.setStyleSheet(f"background-color: {bg_color.name()}; color: {text_color.name()};")
        self.text_color = text_color
        self.message_input.setTextColor(text_color)
        self.saveSettings()

    def add_custom_theme_button(self, layout):
        custom_theme_button = QPushButton("Tema personalizado")
        custom_theme_button.clicked.connect(self.custom_theme_dialog)
        layout.addWidget(custom_theme_button)

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Estilo moderno
    window = ChatWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
