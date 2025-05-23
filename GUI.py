import sys
import paramiko
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QSplitter, QFrame, QGroupBox, QScrollArea,
                             QSplitterHandle)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSettings, QTimer
from PyQt5.QtGui import QColor, QPalette, QFont, QTextCursor

class LocalCommandThread(QThread):
    """Thread for executing local commands and capturing their output"""
    output_received = pyqtSignal(str, int)
    
    def __init__(self, command, terminal_id):
        super().__init__()
        self.command = command
        self.terminal_id = terminal_id
        
    def run(self):
        try:
            # Create subprocess with pipes for stdout/stderr
            process = subprocess.Popen(
                self.command, 
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                executable='/bin/bash'  # Explicitly use bash for shell features
            )
            
            # Read output line by line as it becomes available
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.output_received.emit(output.strip(), self.terminal_id)
            
            # Capture any remaining output after process completes
            remaining_output, errors = process.communicate()
            if remaining_output:
                self.output_received.emit(remaining_output.strip(), self.terminal_id)
            if errors:
                self.output_received.emit(f"Error: {errors.strip()}", self.terminal_id)
                
        except Exception as e:
            self.output_received.emit(f"Command execution failed: {str(e)}", self.terminal_id)

class SSHOutputThread(QThread):
    """Thread for continuously reading SSH shell output"""
    output_received = pyqtSignal(str, int)
    
    def __init__(self, ssh_shell, connection_id):
        super().__init__()
        self.ssh_shell = ssh_shell
        self.connection_id = connection_id
        self._running = True
        
    def run(self):
        while self._running:
            if self.ssh_shell.recv_ready():
                try:
                    # Read data from SSH channel with error handling for decoding
                    data = self.ssh_shell.recv(4096).decode('utf-8', errors='replace')
                    self.output_received.emit(data, self.connection_id)
                except Exception as e:
                    self.output_received.emit(f"\nDecode error: {str(e)}\n", self.connection_id)
            QThread.msleep(50)  # Small delay to prevent CPU overuse
            
    def stop(self):
        """Signal the thread to stop running"""
        self._running = False

class LocalTerminalPanel(QFrame):
    """Panel for local terminal emulation with command input and output display"""
    def __init__(self, terminal_id, parent=None):
        super().__init__(parent)
        self.terminal_id = terminal_id
        self.parent = parent
        self.command_thread = None
        self.initUI()
        
    def initUI(self):
        """Initialize the user interface components"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Create header with terminal label
        header = QHBoxLayout()
        local_label = QLabel(f"Local Terminal {self.terminal_id} - {'For ToF' if self.terminal_id == 1 else 'For Rviz'}")
        local_label.setFont(QFont("Arial", 10, QFont.Bold))
        header.addWidget(local_label)
        header.addStretch()
        layout.addLayout(header)
        
        # Create scrollable output area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.local_output = QTextEdit()
        self.local_output.setReadOnly(True)
        self.local_output.setFont(QFont("Courier New", 10))  # Monospace font for terminal output
        self.local_output.setLineWrapMode(QTextEdit.NoWrap)  # Important for terminal output
        
        # Set dark theme colors
        palette = self.local_output.palette()
        palette.setColor(QPalette.Base, QColor(25, 25, 25))  # Dark background
        palette.setColor(QPalette.Text, QColor(240, 240, 240))  # Light text
        self.local_output.setPalette(palette)
        
        scroll_area.setWidget(self.local_output)
        layout.addWidget(scroll_area)
        
        self.init_local_quick_buttons(layout)
        
        # Command input area
        cmd_layout = QHBoxLayout()
        
        self.local_input = QLineEdit()
        self.local_input.setFont(QFont("Courier New", 10))
        self.local_input.setPlaceholderText('Enter command')
        self.local_input.returnPressed.connect(self.run_local_command)
        cmd_layout.addWidget(self.local_input)
        
        self.local_run_btn = QPushButton('Run')
        self.local_run_btn.setFont(QFont("Arial", 9))
        self.local_run_btn.clicked.connect(self.run_local_command)
        cmd_layout.addWidget(self.local_run_btn)
        
        layout.addLayout(cmd_layout)
    
    def init_local_quick_buttons(self, layout):
        """Initialize quick command buttons specific to each terminal"""
        quick_btn_group = QGroupBox("Control Commands")
        quick_btn_group.setFont(QFont("Arial", 9))
        btn_layout = QHBoxLayout()
        
        if self.terminal_id == 1:
            # ToF-specific commands
            commands = [
                ('Coordinate synchronization', 'ros2 run tf2_ros static_transform_publisher "0" "0" "0" "0" "0" "0" "tof_sensor" "odom"'),
                ('ROS Topic List', 'ros2 topic list'),
                ('Time sync.', 'sudo ntpdate ntp.ubuntu.com'),
                ('Raw ToF Data', 'source ~/tof/Wrappers/ROS2/s50_tof_wrappers/install/setup.bash && ros2 topic echo /raw_tof')
            ]
        else:
            # Rviz/System-specific commands
            commands = [
                ('Rviz', 'ros2 launch turtlebot3_bringup rviz2.launch.py'),
                ('Network', 'ifconfig || ip a'),
                ('Disk Usage', 'df -h'),
                ('System Info', 'uname -a')
            ]
        
        for name, cmd in commands:
            btn = QPushButton(name)
            btn.setFont(QFont("Arial", 8))
            btn.setToolTip(cmd)
            btn.clicked.connect(lambda _, c=cmd: self.execute_local_command(c))
            btn_layout.addWidget(btn)
        
        quick_btn_group.setLayout(btn_layout)
        layout.addWidget(quick_btn_group)
    
    def append_local_output(self, text):
        """Append text to the output display with proper cursor handling"""
        cursor = self.local_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + '\n')
        self.local_output.setTextCursor(cursor)
        self.local_output.ensureCursorVisible()  # Auto-scroll to bottom
    
    def execute_local_command(self, command):
        """Execute a command in a separate thread and handle output"""
        self.append_local_output(f"$ {command}")
        if self.command_thread and self.command_thread.isRunning():
            self.command_thread.terminate()  # Stop any running command
        
        self.command_thread = LocalCommandThread(command, self.terminal_id)
        self.command_thread.output_received.connect(self.parent.handle_local_output)
        self.command_thread.start()
    
    def run_local_command(self):
        """Run the command entered in the input field"""
        command = self.local_input.text().strip()
        if not command:
            return
            
        self.execute_local_command(command)
        self.local_input.clear()

class SSHConnectionPanel(QFrame):
    """Panel for SSH connection management and terminal emulation"""
    def __init__(self, connection_id, parent=None):
        super().__init__(parent)
        self.connection_id = connection_id
        self.ssh_client = None
        self.ssh_shell = None
        self.output_thread = None
        self.connected = False
        self.parent = parent
        self.status_light = None
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.parent.save_connection_info)
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setLineWidth(1)
        
        self.initUI()
        
    def initUI(self):
        """Initialize the user interface components"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Connection header with status indicator
        header = QHBoxLayout()
        self.conn_label = QLabel(f"TurtleBot Terminal {self.connection_id} - {'Robot Control' if self.connection_id == 1 else 'ToF Control'}")
        self.conn_label.setFont(QFont("Arial", 10, QFont.Bold))
        header.addWidget(self.conn_label)
        
        # Status light indicator (green/red)
        self.status_light = QLabel("●")
        self.status_light.setFont(QFont("Arial", 12))
        self.status_light.setVisible(False)
        header.addWidget(self.status_light)
        header.addStretch()
        
        self.connect_btn = QPushButton('Connect')
        self.connect_btn.setFont(QFont("Arial", 9))
        self.connect_btn.clicked.connect(self.toggle_connection)
        header.addWidget(self.connect_btn)
        
        layout.addLayout(header)
        
        # Scrollable output area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(QFont("Courier New", 10))  # Monospace font
        self.output_area.setLineWrapMode(QTextEdit.NoWrap)  # Important for terminal
        
        # Set dark theme colors
        palette = self.output_area.palette()
        palette.setColor(QPalette.Base, QColor(25, 25, 25))  # Dark background
        palette.setColor(QPalette.Text, QColor(240, 240, 240))  # Light text
        self.output_area.setPalette(palette)
        
        scroll_area.setWidget(self.output_area)
        layout.addWidget(scroll_area)
        
        self.init_quick_buttons(layout)
        
        # Command input area with Ctrl+C button
        cmd_layout = QHBoxLayout()
        
        self.stop_btn = QPushButton('Stop (Ctrl+C)')
        self.stop_btn.setFont(QFont("Arial", 9))
        self.stop_btn.clicked.connect(self.send_ctrl_c)
        self.stop_btn.setEnabled(False)
        cmd_layout.addWidget(self.stop_btn)
        
        self.command_input = QLineEdit()
        self.command_input.setFont(QFont("Courier New", 10))
        self.command_input.setPlaceholderText('Enter command')
        self.command_input.setText('')
        self.command_input.returnPressed.connect(self.run_command)
        cmd_layout.addWidget(self.command_input)
        
        self.command_btn = QPushButton('Run')
        self.command_btn.setFont(QFont("Arial", 9))
        self.command_btn.clicked.connect(self.run_command)
        self.command_btn.setEnabled(False)
        cmd_layout.addWidget(self.command_btn)
        
        layout.addLayout(cmd_layout)
    
    def init_quick_buttons(self, layout):
        """Initialize quick command buttons specific to each connection"""
        quick_btn_group = QGroupBox("Control Commands")
        quick_btn_group.setFont(QFont("Arial", 9))
        btn_layout = QHBoxLayout()
        
        if self.connection_id == 1:
            # TurtleBot control commands
            commands = [
                ('Launch TurtleBot 3', 'export TURTLEBOT3_MODEL=burger && ros2 launch turtlebot3_bringup robot.launch.py\n'),
                ('Timesync', 'sudo ntpdate ntp.ubuntu.com\n'),
                ('ROS2 Topics', 'ros2 topic list\n'),
                ('Shutdown TurtleBot 3', 'sudo shutdown"\n')
            ]
        else:
            # ToF sensor control commands
            commands = [
                ('Launch ToF', 'source ~/tof/Wrappers/ROS2/s50_tof_wrappers/install/setup.bash && ros2 launch pointcloud pointcloud.launch.py\n'),
                ('Port Number Check', 'ls /dev/tty*\n'),
                ('Grant port operation permission', 'sudo chmod 777 /dev/\n')
            ]
        
        for name, cmd in commands:
            btn = QPushButton(name)
            btn.setFont(QFont("Arial", 8))
            btn.setToolTip(cmd.strip())
            btn.clicked.connect(lambda _, c=cmd: self.send_command(c))

            # Special styling for shutdown button (red color)
            if name == 'Shutdown TurtleBot 3' and self.connection_id == 1:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FF4444;
                        color: white;
                        border: 1px solid #CC0000;
                        padding: 3px;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #FF6666;
                        border: 1px solid #FF0000;
                    }
                    QPushButton:pressed {
                        background-color: #CC0000;
                    }
                """)

            btn_layout.addWidget(btn)
        
        quick_btn_group.setLayout(btn_layout)
        layout.addWidget(quick_btn_group)
    
    def set_status_light(self, status):
        """Update the connection status light indicator"""
        if status is None:
            self.status_light.setVisible(False)
        else:
            self.status_light.setVisible(True)
            palette = self.status_light.palette()
            palette.setColor(QPalette.WindowText, QColor(0, 255, 0) if status else QColor(255, 0, 0))
            self.status_light.setPalette(palette)
    
    def send_ctrl_c(self):
        """Send Ctrl+C to interrupt current command on remote"""
        if self.connected and self.ssh_shell:
            try:
                self.ssh_shell.send('\x03')  # ASCII code for Ctrl+C
                self.append_output("[Sent Ctrl+C to interrupt current command]")
            except Exception as e:
                self.append_output(f"Error sending Ctrl+C: {str(e)}")
    
    def append_output(self, text):
        """Append text to the output display with proper cursor handling"""
        cursor = self.output_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.output_area.setTextCursor(cursor)
        self.output_area.ensureCursorVisible()  # Auto-scroll to bottom
    
    def handle_output(self, data, connection_id):
        """Handle incoming data from SSH connection"""
        if connection_id == self.connection_id:
            self.append_output(data)
    
    def send_command(self, command):
        """Send command to SSH shell"""
        if not self.connected or not self.ssh_shell:
            self.append_output("Not connected!")
            return
            
        try:
            self.ssh_shell.send(command)
            self.command_input.clear()
        except Exception as e:
            self.append_output(f"Error sending command: {str(e)}")
    
    def run_command(self):
        """Run the command entered in the input field"""
        command = self.command_input.text().strip()
        if not command:
            return
            
        command += "\n"  # Ensure command ends with newline
            
        self.append_output(f"$ {command.strip()}\n")
        self.send_command(command)
    
    def init_environment(self):
        """Initialize remote shell environment with common setup commands"""
        init_commands = [
            "source ~/.bashrc\n",  # Load user environment
            "echo 'Environment initialized'\n",
            "command -v ros2 >/dev/null 2>&1 && echo 'ROS2 detected: $ROS_DISTRO' || echo 'ROS2 not found'\n"
        ]
        
        for cmd in init_commands:
            self.send_command(cmd)
            QThread.msleep(200)  # Small delay between commands
    
    def toggle_connection(self):
        """Toggle SSH connection state (connect/disconnect)"""
        if self.connected:
            self.disconnect_ssh()
        else:
            self.connect_ssh()
        
    def connect_ssh(self):
        """Establish SSH connection to remote host"""
        host = self.parent.ip_input.text().strip()
        username = self.parent.user_input.text().strip()
        password = self.parent.pass_input.text().strip()
        
        if not host or not username:
            self.append_output("Error: IP address and username are required!\n")
            return
            
        self.connect_btn.setEnabled(False)
        self.append_output(f"Connecting to {username}@{host}...\n")
        
        try:
            # Create SSH client and configure
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Auto-add host key
            
            # Connect with timeout
            self.ssh_client.connect(
                host, username=username, password=password,
                look_for_keys=False, allow_agent=False, timeout=10
            )
            
            # Create interactive shell
            self.ssh_shell = self.ssh_client.invoke_shell()
            self.ssh_shell.settimeout(0.1)  # Non-blocking mode
            
            # Start thread to continuously read output
            self.output_thread = SSHOutputThread(self.ssh_shell, self.connection_id)
            self.output_thread.output_received.connect(self.handle_output)
            self.output_thread.start()
            
            # Initialize remote environment
            self.init_environment()
            
            # Update UI state
            self.connected = True
            self.connect_btn.setText('Disconnect')
            self.command_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.set_status_light(True)
            self.append_output("Connected successfully!\n")
            
            self.parent.update_inputs_readonly()
            self.save_timer.start(500)  # Schedule settings save
            
        except Exception as e:
            self.cleanup_connection()
            self.append_output(f"Connection failed: {str(e)}\n")
            self.set_status_light(False)
        finally:
            self.connect_btn.setEnabled(True)
        
    def disconnect_ssh(self):
        """Close SSH connection and clean up resources"""
        self.cleanup_connection()
        self.connected = False
        self.connect_btn.setText('Connect')
        self.command_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.set_status_light(None)
        self.append_output("Disconnected\n")
        
        self.parent.update_inputs_readonly()
    
    def cleanup_connection(self):
        """Clean up SSH connection resources"""
        if self.output_thread:
            self.output_thread.stop()
            self.output_thread.quit()
            self.output_thread.wait()
            self.output_thread = None
            
        if self.ssh_shell:
            self.ssh_shell.close()
            self.ssh_shell = None
            
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None

class SSHClientGUI(QMainWindow):
    """Main application window for the SSH client GUI"""
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MyCompany", "DualSSHClient")  # For persistent settings
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_connection_info)
        self.initUI()
        self.load_connection_info()
        
    def initUI(self):
        """Initialize the main application UI"""
        self.setWindowTitle('Control Pannel for TurtleBot 3 with ToF Sensor')
        self.setFont(QFont("Arial", 9))
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)
        main_widget.setLayout(main_layout)
        
        # Create main splitter for left/right panels
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                width: 0px;
                background: transparent;
            }
        """)
        
        # Left panel (SSH connections)
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_panel.setLayout(left_layout)
        
        # Connection info group
        info_group = QGroupBox("TurtleBot 3 Terminal (Step1)")
        info_group.setFont(QFont("Arial", 9, QFont.Bold))
        info_layout = QHBoxLayout()
        info_group.setLayout(info_layout)
        
        # IP address input
        ip_layout = QVBoxLayout()
        ip_label = QLabel('IP Address:')
        ip_label.setFont(QFont("Arial", 9))
        self.ip_input = QLineEdit()
        self.ip_input.setFont(QFont("Courier New", 10))
        self.ip_input.setPlaceholderText('Enter IP address (e.g., 192.168.1.1)')
        self.ip_input.textChanged.connect(self.schedule_save)
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_input)
        info_layout.addLayout(ip_layout)
        
        # Username input
        user_layout = QVBoxLayout()
        user_label = QLabel('Username:')
        user_label.setFont(QFont("Arial", 9))
        self.user_input = QLineEdit()
        self.user_input.setFont(QFont("Courier New", 10))
        self.user_input.setPlaceholderText('Enter username')
        self.user_input.textChanged.connect(self.schedule_save)
        user_layout.addWidget(user_label)
        user_layout.addWidget(self.user_input)
        info_layout.addLayout(user_layout)
        
        # Password input
        pass_layout = QVBoxLayout()
        pass_label = QLabel('Password:')
        pass_label.setFont(QFont("Arial", 9))
        self.pass_input = QLineEdit()
        self.pass_input.setFont(QFont("Courier New", 10))
        self.pass_input.setPlaceholderText('Enter password')
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.textChanged.connect(self.schedule_save)
        pass_layout.addWidget(pass_label)
        pass_layout.addWidget(self.pass_input)
        info_layout.addLayout(pass_layout)
        
        left_layout.addWidget(info_group)
        
        # SSH terminal panels
        ssh_splitter = QSplitter(Qt.Vertical)
        self.connection1 = SSHConnectionPanel(1, self)
        self.connection2 = SSHConnectionPanel(2, self)
        ssh_splitter.addWidget(self.connection1)
        ssh_splitter.addWidget(self.connection2)
        left_layout.addWidget(ssh_splitter)
        
        # Right panel (local terminals)
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_panel.setLayout(right_layout)
        
        # Local terminal panels
        local_splitter = QSplitter(Qt.Vertical)
        self.local_terminal1 = LocalTerminalPanel(1, self)
        self.local_terminal2 = LocalTerminalPanel(2, self)
        local_splitter.addWidget(self.local_terminal1)
        local_splitter.addWidget(self.local_terminal2)
        right_layout.addWidget(local_splitter)
        
        # Create styled divider between panels
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setLineWidth(3)
        divider.setStyleSheet("""
            QFrame {
                border-left: 1px solid #555;
                border-right: 1px solid #888;
                background: #333;
                margin: 0;
                padding: 0;
            }
        """)
        
        # Add components to main splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(divider)
        main_splitter.addWidget(right_panel)
        
        # Set initial splitter sizes
        main_splitter.setSizes([500, 3, 497])  # Left, divider, right
        local_splitter.setSizes([300, 300])  # Local terminals
        
        main_layout.addWidget(main_splitter)
        self.showMaximized()  # Start maximized
    
    def handle_local_output(self, text, terminal_id):
        """Route local command output to the appropriate terminal"""
        if terminal_id == 1:
            self.local_terminal1.append_local_output(text)
        else:
            self.local_terminal2.append_local_output(text)

    def update_inputs_readonly(self):
        """Update read-only state of connection inputs based on connection status"""
        readonly = self.connection1.connected or self.connection2.connected
        
        self.ip_input.setReadOnly(readonly)
        self.user_input.setReadOnly(readonly)
        self.pass_input.setReadOnly(readonly)
        
        # Visual feedback for disabled state
        for input_field in [self.ip_input, self.user_input, self.pass_input]:
            if readonly:
                input_field.setStyleSheet("background-color: #f0f0f0; color: #808080;")
            else:
                input_field.setStyleSheet("background-color: white; color: black;")
    
    def schedule_save(self):
        """Schedule a save of connection info (debounced)"""
        if not (self.connection1.connected or self.connection2.connected):
            self.save_timer.start(500)  # 500ms delay
        
    def save_connection_info(self):
        """Save connection info to persistent settings"""
        self.settings.setValue("ip", self.ip_input.text())
        self.settings.setValue("username", self.user_input.text())
        self.settings.setValue("password", self.pass_input.text())
        
    def load_connection_info(self):
        """Load connection info from persistent settings"""
        ip = self.settings.value("ip", "")
        username = self.settings.value("username", "")
        password = self.settings.value("password", "")
        
        self.ip_input.setText(ip)
        self.user_input.setText(username)
        self.pass_input.setText(password)
        
    def closeEvent(self, event):
        """Clean up resources when closing the application"""
        self.connection1.cleanup_connection()
        self.connection2.cleanup_connection()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setFont(QFont("Arial", 9))  # Set default font
    gui = SSHClientGUI()
    sys.exit(app.exec_())