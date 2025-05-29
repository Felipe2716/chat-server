import socket
import threading
import sys
import datetime
import os
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTextEdit, QPushButton, QVBoxLayout, 
                           QWidget, QLabel, QLineEdit, QHBoxLayout, QMessageBox, 
                           QTabWidget, QGroupBox, QGridLayout, QComboBox, QCheckBox,
                           QSystemTrayIcon, QMenu, QAction, QStyle, QSplitter)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QSettings
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QColor, QPalette, QPixmap, QTextCharFormat

class ServerThread(QThread):
    update_signal = pyqtSignal(str, str)  # mensaje, tipo
    client_count_signal = pyqtSignal(int)
    
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = []
        self.aliases = []
        self.running = False
    
    def broadcast(self, message, sender_conn=None):
        """Envía un mensaje a todos los clientes conectados excepto al remitente"""
        for client in self.clients:
            if client != sender_conn:  # No enviar mensaje al remitente
                try:
                    client.send(message)
                except:
                    # Si hay un error, eliminar cliente
                    index = self.clients.index(client)
                    self.clients.remove(client)
                    client.close()
                    alias = self.aliases[index]
                    self.aliases.remove(alias)
                    self.broadcast(f'SERVIDOR: {alias} ha dejado el chat!'.encode('utf-8'))
                    self.update_signal.emit(f"[DESCONEXIÓN] {alias} ha dejado el chat", "error")
                    self.client_count_signal.emit(len(self.clients))
    
    def handle_client(self, conn, addr, alias):
        """Maneja la comunicación con un cliente individual"""
        self.update_signal.emit(f"[CONEXIÓN] {addr[0]}:{addr[1]} se ha conectado como {alias}", "success")
        
        # Notificar a todos que el cliente se ha unido
        self.broadcast(f"SERVIDOR: {alias} se ha unido al chat!".encode('utf-8'))
        
        # Enviar mensaje de bienvenida al cliente
        conn.send("SERVIDOR: ¡Bienvenido al chat! Escribe 'salir' para desconectarte.".encode('utf-8'))
        
        connected = True
        while connected and self.running:
            try:
                # Recibir mensaje
                message = conn.recv(1024)
                if message:
                    # Si el mensaje es 'salir', desconectar cliente
                    if message.decode('utf-8').lower() == 'salir':
                        connected = False
                    else:
                        # Formato: alias: mensaje
                        formatted_msg = f"{alias}: {message.decode('utf-8')}"
                        self.broadcast(formatted_msg.encode('utf-8'), conn)
                        self.update_signal.emit(f"[MENSAJE] {formatted_msg}", "info")
                else:
                    connected = False
            except:
                connected = False
        
        # Cliente desconectado
        self.update_signal.emit(f"[DESCONEXIÓN] {alias} se ha desconectado", "error")
        if conn in self.clients:
            index = self.clients.index(conn)
            self.clients.remove(conn)
            conn.close()
            alias = self.aliases[index]
            self.broadcast(f'SERVIDOR: {alias} ha dejado el chat!'.encode('utf-8'))
            self.aliases.remove(alias)
            self.client_count_signal.emit(len(self.clients))
    
    def run(self):
        """Inicia el servidor en un hilo separado"""
        self.running = True
        self.update_signal.emit(f"[INICIANDO] El servidor está iniciando en {self.host}:{self.port}...", "system")
        
        # Creamos un objeto socket tipo TCP
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Configurar el socket para reutilizar dirección
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.update_signal.emit(f"[ACTIVO] Servidor activo en {self.host}:{self.port}", "success")
        except Exception as e:
            self.update_signal.emit(f"[ERROR] Error al iniciar el servidor: {str(e)}", "error")
            return
        
        self.server_socket.listen(5)
        self.update_signal.emit("[ESCUCHANDO] Esperando conexiones...", "system")
        
        # Configurar tiempo de espera para poder cerrar el hilo correctamente
        self.server_socket.settimeout(1)
        
        while self.running:
            try:
                # Aceptar conexiones
                conn, addr = self.server_socket.accept()
                
                # Solicitar nombre de usuario
                conn.send("ALIAS".encode('utf-8'))
                alias = conn.recv(1024).decode('utf-8')
                
                # Almacenar conexión y alias
                self.clients.append(conn)
                self.aliases.append(alias)
                self.client_count_signal.emit(len(self.clients))
                
                # Iniciar un hilo para manejar el cliente
                thread = threading.Thread(target=self.handle_client, args=(conn, addr, alias))
                thread.daemon = True
                thread.start()
                
                self.update_signal.emit(f"[CONEXIONES ACTIVAS] {len(self.clients)}", "info")
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.update_signal.emit(f"[ERROR] Error al aceptar conexión: {str(e)}", "error")
        
        # Cerrar todas las conexiones al detener el servidor
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        
        if self.server_socket:
            self.server_socket.close()
            self.update_signal.emit("[DETENIDO] Servidor detenido correctamente", "system")
    
    def stop(self):
        """Detiene el servidor"""
        self.running = False
        # Esperar a que el hilo termine
        self.wait()

class ServerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.is_dark_mode = True  # Por defecto, tema oscuro
        self.settings = QSettings("ChatApp", "Server")
        self.loadSettings()
        self.initUI()
        self.setupTrayIcon()
        self.applyTheme()
    
    def loadSettings(self):
        """Carga configuraciones guardadas"""
        self.is_dark_mode = self.settings.value("darkMode", True, type=bool)
        # Usar 0.0.0.0 por defecto para Render
        default_host = os.environ.get("RENDER", None) and "0.0.0.0" or "172.20.10.12"
        self.host = self.settings.value("host", default_host, type=str)
        # Usar puerto de variable de entorno PORT si existe, sino 10000
        default_port = os.environ.get("PORT", "10000")
        self.port = self.settings.value("port", default_port, type=str)
        self.auto_start = self.settings.value("autoStart", False, type=bool)
        self.minimize_to_tray = self.settings.value("minimizeToTray", False, type=bool)
    
    def saveSettings(self):
        """Guarda configuraciones"""
        self.settings.setValue("darkMode", self.is_dark_mode)
        self.settings.setValue("host", self.host_input.text())
        self.settings.setValue("port", self.port_input.text())
        self.settings.setValue("autoStart", self.auto_start_checkbox.isChecked())
        self.settings.setValue("minimizeToTray", self.tray_checkbox.isChecked())
    
    def initUI(self):
        """Configura la interfaz de usuario"""
        self.setWindowTitle("Servidor de Chat v2.0")
        self.setGeometry(300, 300, 900, 700)
        
        # Icono de la aplicación
        self.setWindowIcon(QIcon('server.png'))
        
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
            logo_pixmap = QPixmap('server_logo.png').scaledToHeight(50, Qt.SmoothTransformation)
            logo_label.setPixmap(logo_pixmap)
            header_layout.addWidget(logo_label)
        except:
            # Si no hay logo, añadir un espaciador
            header_layout.addSpacing(20)
        
        # Título
        title_label = QLabel("SERVIDOR DE CHAT")
        title_label.setFont(QFont("Montserrat", 20, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label, 1)
        
        # Panel de estado
        status_box = QGroupBox("Estado")
        status_layout = QVBoxLayout(status_box)
        
        self.status_label = QLabel("Inactivo")
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.status_label.setStyleSheet("color: #CF6679;")  # Rojo para inactivo
        self.status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_label)
        
        self.client_count = QLabel("0 clientes conectados")
        self.client_count.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.client_count)
        
        header_layout.addWidget(status_box)
        
        main_layout.addLayout(header_layout)
        
        # Pestañas
        tab_widget = QTabWidget()
        
        # Tab Principal
        main_tab = QWidget()
        main_tab_layout = QVBoxLayout(main_tab)
        
        # Grupo de configuración
        config_group = QGroupBox("Configuración del Servidor")
        config_layout = QGridLayout(config_group)
        
        config_layout.addWidget(QLabel("Dirección IP:"), 0, 0)
        self.host_input = QLineEdit()
        self.host_input.setText(self.host)
        config_layout.addWidget(self.host_input, 0, 1)
        
        config_layout.addWidget(QLabel("Puerto:"), 0, 2)
        self.port_input = QLineEdit()
        self.port_input.setText(self.port)
        config_layout.addWidget(self.port_input, 0, 3)
        
        # Botones de control
        self.start_button = QPushButton("INICIAR SERVIDOR")
        self.start_button.setIcon(QIcon('start.png'))
        self.start_button.setMinimumHeight(40)
        self.start_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.start_button.setStyleSheet("""
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
        self.start_button.clicked.connect(self.start_server)
        config_layout.addWidget(self.start_button, 1, 0, 1, 2)
        
        self.stop_button = QPushButton("DETENER SERVIDOR")
        self.stop_button.setIcon(QIcon('stop.png'))
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.stop_button.setStyleSheet("""
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
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        config_layout.addWidget(self.stop_button, 1, 2, 1, 2)
        
        main_tab_layout.addWidget(config_group)
        
        # Grupo de registro de actividad
        log_group = QGroupBox("Registro de Actividad")
        log_layout = QVBoxLayout(log_group)
        
        # Área de registro
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 10))
        log_layout.addWidget(self.log_area)
        
        main_tab_layout.addWidget(log_group, 1)  # Dar más espacio al registro
        
        # Añadir la pestaña principal
        tab_widget.addTab(main_tab, "Principal")
        
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
        self.auto_start_checkbox = QCheckBox("Iniciar servidor automáticamente al abrir")
        self.auto_start_checkbox.setChecked(self.auto_start)
        options_layout.addWidget(self.auto_start_checkbox)
        
        self.tray_checkbox = QCheckBox("Minimizar a bandeja del sistema al cerrar")
        self.tray_checkbox.setChecked(self.minimize_to_tray)
        options_layout.addWidget(self.tray_checkbox)
        
        settings_layout.addWidget(options_group)
        settings_layout.addStretch()
        
        # Añadir la pestaña de configuración
        tab_widget.addTab(settings_tab, "Configuración")
        
        main_layout.addWidget(tab_widget)
        
        # Barra de estado
        self.statusBar().showMessage("Servidor de Chat listo")
        
        # Información del desarrollador
        dev_layout = QHBoxLayout()
        dev_info = QLabel("© " + str(datetime.datetime.now().year) + " - Servidor de Chat con PyQt5")
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
    
    def setupTrayIcon(self):
        """Configura el icono de la bandeja del sistema"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('server.png'))
        
        # Menú contextual para el icono de la bandeja
        tray_menu = QMenu()
        
        show_action = QAction("Mostrar", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        status_action = QAction("Servidor Inactivo", self)
        status_action.setEnabled(False)
        self.tray_status_action = status_action
        tray_menu.addAction(status_action)
        
        tray_menu.addSeparator()
        
        start_action = QAction("Iniciar Servidor", self)
        start_action.triggered.connect(self.start_server)
        self.tray_start_action = start_action
        tray_menu.addAction(start_action)
        
        stop_action = QAction("Detener Servidor", self)
        stop_action.triggered.connect(self.stop_server)
        stop_action.setEnabled(False)
        self.tray_stop_action = stop_action
        tray_menu.addAction(stop_action)
        
        tray_menu.addSeparator()
        
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.force_quit)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
    
    def tray_icon_activated(self, reason):
        """Maneja los clics en el icono de la bandeja"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.activateWindow()
    
    def update_time(self):
        """Actualiza el tiempo en la barra de estado"""
        current_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.statusBar().showMessage(f"Servidor de Chat | {current_time}")
    
    def change_theme(self, index):
        """Cambia el tema según la selección del combobox"""
        self.is_dark_mode = (index == 0)
        self.applyTheme()
    
    def toggle_theme(self):
        """Cambia entre tema claro y oscuro"""
        self.is_dark_mode = not self.is_dark_mode
        self.theme_combo.setCurrentIndex(0 if self.is_dark_mode else 1)
        self.applyTheme()
    
    def applyTheme(self):
        """Aplica el tema seleccionado"""
        if self.is_dark_mode:
            # Tema oscuro
            dark_palette = QPalette()
            dark_color = QColor(45, 45, 45)
            dark_palette.setColor(QPalette.Window, dark_color)
            dark_palette.setColor(QPalette.WindowText, Qt.white)
            dark_palette.setColor(QPalette.Base, QColor(30, 30, 30))
            dark_palette.setColor(QPalette.AlternateBase, dark_color)
            dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
            dark_palette.setColor(QPalette.ToolTipText, Qt.white)
            dark_palette.setColor(QPalette.Text, Qt.white)
            dark_palette.setColor(QPalette.Button, dark_color)
            dark_palette.setColor(QPalette.ButtonText, Qt.white)
            dark_palette.setColor(QPalette.BrightText, Qt.red)
            dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.HighlightedText, Qt.black)
            
            QApplication.setPalette(dark_palette)
            self.setStyleSheet("""
                QMainWindow, QDialog {
                    background-color: #2D2D2D;
                }
                QGroupBox {
                    border: 1px solid #555;
                    border-radius: 5px;
                    margin-top: 1ex;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top center;
                    padding: 0 5px;
                    color: #BB86FC;
                }
                QTextEdit {
                    background-color: #1E1E1E;
                    color: #E0E0E0;
                    border: 1px solid #555;
                    border-radius: 2px;
                }
                QTabWidget::pane {
                    border: 1px solid #555;
                    border-radius: 3px;
                }
                QTabBar::tab {
                    background-color: #3D3D3D;
                    color: #E0E0E0;
                    padding: 8px 12px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #BB86FC;
                    color: #1E1E1E;
                    font-weight: bold;
                }
                QComboBox, QLineEdit {
                    background-color: #3D3D3D;
                    color: #E0E0E0;
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 5px;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                }
                QCheckBox {
                    color: #E0E0E0;
                }
                QStatusBar {
                    background-color: #1E1E1E;
                    color: #BB86FC;
                }
            """)
        else:
            # Tema claro
            light_palette = QPalette()
            QApplication.setPalette(light_palette)
            self.setStyleSheet("""
                QMainWindow, QDialog {
                    background-color: #F5F5F5;
                }
                QGroupBox {
                    border: 1px solid #BDBDBD;
                    border-radius: 5px;
                    margin-top: 1ex;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top center;
                    padding: 0 5px;
                    color: #1976D2;
                }
                QTextEdit {
                    background-color: white;
                    color: #212121;
                    border: 1px solid #BDBDBD;
                    border-radius: 2px;
                }
                QTabWidget::pane {
                    border: 1px solid #BDBDBD;
                    border-radius: 3px;
                }
                QTabBar::tab {
                    background-color: #E0E0E0;
                    color: #212121;
                    padding: 8px 12px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }
                QTabBar::tab:selected {
                    background-color: #2196F3;
                    color: white;
                    font-weight: bold;
                }
                QComboBox, QLineEdit {
                    background-color: white;
                    color: #212121;
                    border: 1px solid #BDBDBD;
                    border-radius: 3px;
                    padding: 5px;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                }
                QCheckBox {
                    color: #212121;
                }
                QStatusBar {
                    background-color: #E0E0E0;
                    color: #1976D2;
                }
            """)
    
    def append_log(self, message, type="info"):
        """Añade un mensaje al área de registro con formato por tipo"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Define formatos para diferentes tipos de mensajes
        format_map = {
            "info": (QColor("#E0E0E0") if self.is_dark_mode else QColor("#212121"), QFont.Normal),
            "success": (QColor("#4CAF50"), QFont.Bold),
            "error": (QColor("#F44336"), QFont.Bold),
            "system": (QColor("#2196F3"), QFont.Normal),
            "warning": (QColor("#FF9800"), QFont.Bold)
        }
        
        # Aplicar formato
        color, weight = format_map.get(type, format_map["info"])
        
        # Construir mensaje con HTML para formato
        formatted_time = f'<span style="color: #888888;">[{current_time}]</span>'
        
        if type == "success":
            icon = "✓ "
        elif type == "error":
            icon = "✗ "
        elif type == "warning":
            icon = "⚠ "
        elif type == "system":
            icon = "ℹ "
        else:
            icon = ""
        
        formatted_message = f'<span style="color: {color.name()}; font-weight: {"bold" if weight == QFont.Bold else "normal"};">{icon}{message}</span>'
        
        # Añadir mensaje formateado
        self.log_area.append(f"{formatted_time} {formatted_message}")
        
        # Auto-scroll al final
        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_area.setTextCursor(cursor)
    
    def start_server(self):
        """Inicia el servidor"""
        if not self.server_thread or not self.server_thread.isRunning():
            try:
                # Usar host y puerto de entorno si existen
                host = os.environ.get("PORT") and "0.0.0.0" or self.host_input.text()
                port = int(os.environ.get("PORT", self.port_input.text()))
                # Validar entradas
                if not host:
                    QMessageBox.warning(self, "Advertencia", "Por favor, ingrese una dirección IP válida.")
                    return
                self.server_thread = ServerThread(host, port)
                self.server_thread.update_signal.connect(self.append_log)
                self.server_thread.client_count_signal.connect(self.update_client_count)
                self.server_thread.start()
                
                # Actualizar interfaz
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.host_input.setEnabled(False)
                self.port_input.setEnabled(False)
                self.status_label.setText("Activo")
                self.status_label.setStyleSheet("color: #4CAF50;")  # Verde para activo
                
                # Actualizar acciones del tray
                self.tray_start_action.setEnabled(False)
                self.tray_stop_action.setEnabled(True)
                self.tray_status_action.setText("Servidor Activo")
                
                # Mostrar notificación
                if self.tray_icon.isVisible():
                    self.tray_icon.showMessage("Servidor de Chat", "Servidor iniciado correctamente", 
                                             QSystemTrayIcon.Information, 3000)
                
                # Guardar configuración
                self.saveSettings()
                
            except ValueError:
                QMessageBox.warning(self, "Error", "El puerto debe ser un número entero.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al iniciar el servidor: {str(e)}")
    
    def update_client_count(self, count):
        """Actualiza el contador de clientes conectados"""
        self.client_count.setText(f"{count} cliente{'s' if count != 1 else ''} conectado{'s' if count != 1 else ''}")
    
    def stop_server(self):
        """Detiene el servidor"""
        if self.server_thread and self.server_thread.isRunning():
            self.server_thread.stop()
            
            # Actualizar interfaz
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.host_input.setEnabled(True)
            self.port_input.setEnabled(True)
            self.status_label.setText("Inactivo")
            self.status_label.setStyleSheet("color: #CF6679;")  # Rojo para inactivo
            
            # Actualizar contador de clientes
            self.client_count.setText("0 clientes conectados")
            
            # Actualizar acciones del tray
            self.tray_start_action.setEnabled(True)
            self.tray_stop_action.setEnabled(False)
            self.tray_status_action.setText("Servidor Inactivo")
            
            # Mostrar notificación
            if self.tray_icon.isVisible():
                self.tray_icon.showMessage("Servidor de Chat", "Servidor detenido correctamente", 
                                         QSystemTrayIcon.Information, 3000)
    
    def force_quit(self):
        """Cierra completamente la aplicación"""
        if self.server_thread and self.server_thread.isRunning():
            self.server_thread.stop()
        QApplication.quit()
    
    def closeEvent(self, event):
        """Maneja el evento de cierre de la ventana"""
        # Guardar configuración
        self.saveSettings()
        
        if self.server_thread and self.server_thread.isRunning():
            reply = QMessageBox.question(self, 'Confirmar salida', 
                '¿Está seguro que desea cerrar el servidor?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                if self.tray_checkbox.isChecked():
                    event.ignore()
                    self.hide()
                    self.tray_icon.show()
                    self.tray_icon.showMessage("Servidor de Chat", 
                                             "El servidor sigue ejecutándose en segundo plano", 
                                             QSystemTrayIcon.Information, 3000)
                else:
                    self.stop_server()
                    event.accept()
            else:
                event.ignore()
        else:
            if self.tray_checkbox.isChecked():
                event.ignore()
                self.hide()
                self.tray_icon.show()
            else:
                event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Estilo moderno
    window = ServerWindow()
    window.show()
    
    # Comprobar inicio automático
    if window.auto_start_checkbox.isChecked():
        QTimer.singleShot(500, window.start_server)
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()