import os
import sys
import time
import threading
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageGrab
import customtkinter as ctk

# Import native OCR engine
from ocr_engine import recognize_text_from_bytes

# Set theme and color options
ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"

# Brand Color Palette (Indigo/Slate modern aesthetic)
COLOR_ACCENT_LIGHT = "#6366f1"  # Indigo-500
COLOR_ACCENT_DARK = "#818cf8"   # Indigo-400
COLOR_ACCENT_HOVER_LIGHT = "#4f46e5"  # Indigo-600
COLOR_ACCENT_HOVER_DARK = "#6366f1"   # Indigo-500

COLOR_BG_LIGHT = "#f8fafc"      # Slate-50
COLOR_BG_DARK = "#0f172a"       # Slate-900

COLOR_CARD_LIGHT = "#ffffff"    # Pure White
COLOR_CARD_DARK = "#1e293b"     # Slate-800

COLOR_BORDER_LIGHT = "#e2e8f0"  # Slate-200
COLOR_BORDER_DARK = "#334155"   # Slate-700

COLOR_TEXT_LIGHT = "#0f172a"    # Slate-900
COLOR_TEXT_DARK = "#f1f5f9"     # Slate-100

class ScreenshotSelector:
    """
    Retina-aware, borderless full-screen overlay for screenshot capture.
    Avoids creating a new macOS Desktop Space and handles high-DPI scaling.
    """
    def __init__(self, parent, on_screenshot_captured, on_cancel=None):
        self.parent = parent
        self.on_screenshot_captured = on_screenshot_captured
        self.on_cancel = on_cancel
        
        # 1. Grab full screen screenshot (captures raw physical pixels)
        self.original_screenshot = ImageGrab.grab(all_screens=True)
        self.shot_w, self.shot_h = self.original_screenshot.size
        
        # 2. Get logical screen dimensions
        self.logical_w = parent.winfo_screenwidth()
        self.logical_h = parent.winfo_screenheight()
        
        # 3. Calculate scaling ratio between physical capture and logical display
        self.scale_x = self.shot_w / self.logical_w if self.logical_w > 0 else 1.0
        self.scale_y = self.shot_h / self.logical_h if self.logical_h > 0 else 1.0
        
        # 4. Downsample screenshot to logical size for canvas preview and interactive drawing
        self.display_bg = self.original_screenshot.resize((self.logical_w, self.logical_h), Image.Resampling.LANCZOS)
        
        # Create darkened backdrop overlay
        self.darkened_screenshot = self.display_bg.convert("RGBA")
        overlay = Image.new("RGBA", (self.logical_w, self.logical_h), (0, 0, 0, 110))  # 110 alpha mask
        self.darkened_screenshot = Image.alpha_composite(self.darkened_screenshot, overlay).convert("RGB")
        
        self.bg_photo = ImageTk.PhotoImage(self.darkened_screenshot)
        
        # 5. Create borderless top-level window
        self.top = tk.Toplevel(parent)
        self.top.overrideredirect(True)  # Crucial: Avoids new macOS Desktop space slide transition
        self.top.geometry(f"{self.logical_w}x{self.logical_h}+0+0")
        self.top.attributes('-topmost', True)
        self.top.config(cursor="cross")
        
        # Canvas for interactive drawing
        self.canvas = tk.Canvas(self.top, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_photo)
        
        # States
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.bright_img_id = None
        self.bright_photo = None
        
        # Event binds
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.top.bind("<Escape>", self.cancel)
        self.canvas.bind("<ButtonPress-3>", self.cancel)  # Right-click cancels
        
        # Focus force for keyboard events (like Escape)
        self.top.focus_force()

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, 
            outline="#818cf8", width=2, dash=(4, 4)
        )

    def on_move_press(self, event):
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)
        
        x1, y1 = min(self.start_x, cur_x), min(self.start_y, cur_y)
        x2, y2 = max(self.start_x, cur_x), max(self.start_y, cur_y)
        
        # Real-time preview of selection using scaled display background (buttery smooth)
        if (x2 - x1) > 2 and (y2 - y1) > 2:
            cropped = self.display_bg.crop((x1, y1, x2, y2))
            self.bright_photo = ImageTk.PhotoImage(cropped)
            if self.bright_img_id:
                self.canvas.delete(self.bright_img_id)
            self.bright_img_id = self.canvas.create_image(x1, y1, anchor="nw", image=self.bright_photo)
            self.canvas.tag_raise(self.rect_id)

    def on_button_release(self, event):
        end_x, end_y = event.x, event.y
        x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
        x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        
        self.top.destroy()
        
        if (x2 - x1) > 5 and (y2 - y1) > 5:
            # Map logical selection coordinates back to high-res physical coordinates for OCR accuracy
            orig_x1 = int(x1 * self.scale_x)
            orig_y1 = int(y1 * self.scale_y)
            orig_x2 = int(x2 * self.scale_x)
            orig_y2 = int(y2 * self.scale_y)
            
            cropped_image = self.original_screenshot.crop((orig_x1, orig_y1, orig_x2, orig_y2))
            self.on_screenshot_captured(cropped_image)
        else:
            if self.on_cancel:
                self.on_cancel()

    def cancel(self, event=None):
        self.top.destroy()
        if self.on_cancel:
            self.on_cancel()


class LiteOcrApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Lite OCR - 极简文字识别")
        self.geometry("980x660")
        self.minsize(850, 550)
        
        # Apply custom theme window background
        self.configure(fg_color=(COLOR_BG_LIGHT, COLOR_BG_DARK))
        
        # State variables
        self.current_image = None       # PIL Image
        self.raw_ocr_lines = []         # Unmerged OCR result lines
        self.last_clipboard_hash = None # To prevent redundant OCR on window focus
        
        # Configure layout grids
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Create Widgets
        self.setup_header()
        self.setup_main_layout()
        self.setup_status_bar()
        
        # Key bindings
        self.bind("<Control-v>", lambda e: self.import_from_clipboard())
        self.bind("<Control-V>", lambda e: self.import_from_clipboard())
        self.bind("<Control-o>", lambda e: self.import_file())
        self.bind("<Control-O>", lambda e: self.import_file())
        self.bind("<F1>", lambda e: self.start_screenshot())
        
        # Monitor Window Activation (for Auto Clipboard OCR)
        self.bind("<<Activate>>", self.on_window_activate)
        self.bind("<FocusIn>", self.on_window_activate)
        
        # Start clipboard polling fallback loop
        self.after(500, self.poll_clipboard)

    def setup_header(self):
        """Header Action Bar with Title and Actions"""
        self.header_frame = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 5))
        
        # --- Brand Title & Logo ---
        self.title_container = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.title_container.pack(side="left", fill="y")
        
        self.lbl_logo = ctk.CTkLabel(
            self.title_container, text="✨ LITE OCR", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 20, "bold"),
            text_color=(COLOR_ACCENT_LIGHT, COLOR_ACCENT_DARK)
        )
        self.lbl_logo.pack(anchor="w", pady=(0, 2))
        
        self.lbl_subtitle = ctk.CTkLabel(
            self.title_container, text="免安装 · 系统级原生文本识别", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 11),
            text_color=("gray60", "gray50")
        )
        self.lbl_subtitle.pack(anchor="w")
        
        # --- Action Buttons Container ---
        self.actions_container = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.actions_container.pack(side="right", fill="y")
        
        # Theme Switcher
        self.theme_switch = ctk.CTkSwitch(
            self.actions_container, text="深色模式", font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 11),
            command=self.toggle_theme, onvalue="on", offvalue="off",
            progress_color=(COLOR_ACCENT_LIGHT, COLOR_ACCENT_DARK)
        )
        self.theme_switch.pack(side="right", padx=(15, 5), pady=10)
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()

        # Separator line
        self.sep = ctk.CTkFrame(self.actions_container, width=1, height=24, fg_color=(COLOR_BORDER_LIGHT, COLOR_BORDER_DARK))
        self.sep.pack(side="right", padx=15, pady=8)

        # Primary Action: Screenshot
        self.btn_screenshot = ctk.CTkButton(
            self.actions_container, text="📸 屏幕截图 (F1)", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 13, "bold"),
            fg_color=(COLOR_ACCENT_LIGHT, COLOR_ACCENT_DARK),
            hover_color=(COLOR_ACCENT_HOVER_LIGHT, COLOR_ACCENT_HOVER_DARK),
            text_color="#ffffff",
            command=self.start_screenshot, width=140, height=36, corner_radius=8
        )
        self.btn_screenshot.pack(side="right", padx=4)
        
        # Secondary Action: Import File
        self.btn_file = ctk.CTkButton(
            self.actions_container, text="📁 选择图片", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 12),
            command=self.import_file, width=110, height=36, corner_radius=8,
            fg_color=(COLOR_BORDER_LIGHT, COLOR_BORDER_DARK),
            text_color=(COLOR_TEXT_LIGHT, COLOR_TEXT_DARK),
            hover_color=("#cbd5e1", "#475569")
        )
        self.btn_file.pack(side="right", padx=4)
        
        # Secondary Action: Clipboard OCR
        self.btn_clipboard = ctk.CTkButton(
            self.actions_container, text="📋 粘贴识别", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 12),
            command=self.import_from_clipboard, width=110, height=36, corner_radius=8,
            fg_color=(COLOR_BORDER_LIGHT, COLOR_BORDER_DARK),
            text_color=(COLOR_TEXT_LIGHT, COLOR_TEXT_DARK),
            hover_color=("#cbd5e1", "#475569")
        )
        self.btn_clipboard.pack(side="right", padx=4)

    def setup_main_layout(self):
        """Split layout with modern card styling and layout hierarchy"""
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(5, 10))
        
        self.main_frame.grid_columnconfigure(0, weight=10)  # Left Preview Card
        self.main_frame.grid_columnconfigure(1, weight=11)  # Right Result Card
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        # ==========================================
        # LEFT CARD: Image Viewer
        # ==========================================
        self.left_panel = ctk.CTkFrame(
            self.main_frame, corner_radius=12,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1,
            border_color=(COLOR_BORDER_LIGHT, COLOR_BORDER_DARK)
        )
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(0, weight=1)
        
        # Beautiful Vector Placeholder
        self.placeholder_container = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.placeholder_container.grid(row=0, column=0)
        
        self.lbl_placeholder_icon = ctk.CTkLabel(
            self.placeholder_container, text="📥", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 48)
        )
        self.lbl_placeholder_icon.pack(pady=10)
        
        self.lbl_placeholder_text = ctk.CTkLabel(
            self.placeholder_container, text="拖入图片文件 或 粘贴截图", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 14, "bold"),
            text_color=(COLOR_TEXT_LIGHT, COLOR_TEXT_DARK)
        )
        self.lbl_placeholder_text.pack(pady=2)
        
        self.lbl_placeholder_sub = ctk.CTkLabel(
            self.placeholder_container, text="支持 PNG, JPG, BMP 等常用格式\n按下 [F1] 或 [Ctrl+V] 快捷导入", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 11),
            text_color="gray", justify="center"
        )
        self.lbl_placeholder_sub.pack(pady=5)
        
        # Actual Image Display Label (starts hidden)
        self.image_display = ctk.CTkLabel(self.left_panel, text="")
        
        # Binding window resize to scale the image preview dynamically
        self.left_panel.bind("<Configure>", self.on_preview_resize)
        
        # ==========================================
        # RIGHT CARD: Text Results
        # ==========================================
        self.right_panel = ctk.CTkFrame(
            self.main_frame, corner_radius=12,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1,
            border_color=(COLOR_BORDER_LIGHT, COLOR_BORDER_DARK)
        )
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(1, weight=1)  # Text box occupies space
        
        # --- Sub Header Settings Panel ---
        self.settings_card = ctk.CTkFrame(
            self.right_panel, height=48, corner_radius=8,
            fg_color=(COLOR_BG_LIGHT, COLOR_BG_DARK),
            border_width=1,
            border_color=(COLOR_BORDER_LIGHT, COLOR_BORDER_DARK)
        )
        self.settings_card.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 10))
        
        self.switch_merge = ctk.CTkSwitch(
            self.settings_card, text="合并段落", font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 11),
            command=self.update_ocr_textbox_display,
            progress_color=(COLOR_ACCENT_LIGHT, COLOR_ACCENT_DARK)
        )
        self.switch_merge.pack(side="left", padx=12, pady=8)
        self.switch_merge.select()  # Default ON
        
        self.switch_autocopy = ctk.CTkSwitch(
            self.settings_card, text="自动复制结果", font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 11),
            progress_color=(COLOR_ACCENT_LIGHT, COLOR_ACCENT_DARK)
        )
        self.switch_autocopy.pack(side="left", padx=12, pady=8)
        self.switch_autocopy.select()  # Default ON
        
        self.switch_autolistener = ctk.CTkSwitch(
            self.settings_card, text="激活窗口自动识别", font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 11),
            progress_color=(COLOR_ACCENT_LIGHT, COLOR_ACCENT_DARK)
        )
        self.switch_autolistener.pack(side="left", padx=12, pady=8)
        
        # Switch Variable Configuration
        self.auto_listener_var = tk.BooleanVar(value=True)
        self.switch_autolistener.configure(variable=self.auto_listener_var)
        
        # --- OCR Output Textbox ---
        self.txt_result = ctk.CTkTextbox(
            self.right_panel, 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 13), 
            wrap="word",
            fg_color="transparent",
            text_color=(COLOR_TEXT_LIGHT, COLOR_TEXT_DARK)
        )
        # Inner text box padding and placement
        self.txt_result.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 15))
        
        # --- Bottom Control Toolbar ---
        self.text_controls = ctk.CTkFrame(self.right_panel, height=45, fg_color="transparent")
        self.text_controls.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 15))
        
        # Primary Copy Button
        self.btn_copy = ctk.CTkButton(
            self.text_controls, text="📋 复制文本", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 12, "bold"),
            command=self.copy_to_clipboard, width=110, height=34, corner_radius=8,
            fg_color=(COLOR_ACCENT_LIGHT, COLOR_ACCENT_DARK),
            hover_color=(COLOR_ACCENT_HOVER_LIGHT, COLOR_ACCENT_HOVER_DARK),
            text_color="#ffffff"
        )
        self.btn_copy.pack(side="right", padx=4)
        
        # Save Text Button
        self.btn_save = ctk.CTkButton(
            self.text_controls, text="💾 保存本地", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 12),
            command=self.save_text_file, width=110, height=34, corner_radius=8,
            fg_color=(COLOR_BORDER_LIGHT, COLOR_BORDER_DARK),
            text_color=(COLOR_TEXT_LIGHT, COLOR_TEXT_DARK),
            hover_color=("#cbd5e1", "#475569")
        )
        self.btn_save.pack(side="right", padx=4)
        
        # Red-Soft Clear Button
        self.btn_clear = ctk.CTkButton(
            self.text_controls, text="🧹 清空", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 12),
            command=self.clear_all, width=80, height=34, corner_radius=8,
            fg_color=("#fee2e2", "#7f1d1d"), 
            text_color=("#991b1b", "#fecaca"),
            hover_color=("#fecaca", "#991b1b")
        )
        self.btn_clear.pack(side="left", padx=0)

    def setup_status_bar(self):
        """Elegant pill-shaped status indicator bar"""
        self.status_container = ctk.CTkFrame(
            self, height=32, corner_radius=8,
            fg_color=(COLOR_CARD_LIGHT, COLOR_CARD_DARK),
            border_width=1,
            border_color=(COLOR_BORDER_LIGHT, COLOR_BORDER_DARK)
        )
        self.status_container.grid(row=2, column=0, sticky="ew", padx=20, pady=(5, 15))
        
        self.lbl_status = ctk.CTkLabel(
            self.status_container, text="就绪 · 等待图像载入...", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 11), 
            text_color="gray"
        )
        self.lbl_status.pack(side="left", padx=12, pady=4)
        
        self.lbl_info = ctk.CTkLabel(
            self.status_container, text="F1 开始截图 | Ctrl+V 粘贴图片 | 本地系统原生 OCR", 
            font=("Segoe UI" if sys.platform == "win32" else "PingFang SC", 11), 
            text_color="gray50"
        )
        self.lbl_info.pack(side="right", padx=12, pady=4)

    # --- THEME MANAGEMENT ---
    def toggle_theme(self):
        state = self.theme_switch.get()
        if state == "on":
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    # --- IMAGE IMPORT AND DISPLAY ---
    def load_image(self, img: Image.Image):
        """Save the raw image and trigger visualization and OCR."""
        self.current_image = img
        self.placeholder_container.grid_remove()
        self.image_display.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        
        # Trigger redraw of preview
        self.update_image_preview()
        
        # Trigger OCR analysis in background thread
        self.lbl_status.configure(text="正在进行 OCR 识别，请稍候...", text_color=(COLOR_ACCENT_LIGHT, COLOR_ACCENT_DARK))
        self.txt_result.delete("1.0", tk.END)
        self.txt_result.insert("1.0", "正在解析文字，请稍候...\n")
        
        # Run in worker thread so Tkinter UI is fully responsive
        thread = threading.Thread(target=self.perform_ocr_thread, args=(img,))
        thread.daemon = True
        thread.start()

    def update_image_preview(self):
        """Resize image to fit into the left panel container while maintaining aspect ratio."""
        if not self.current_image:
            return
            
        panel_w = self.left_panel.winfo_width() - 24
        panel_h = self.left_panel.winfo_height() - 24
        
        # Prevent division by zero or negative size
        if panel_w <= 10 or panel_h <= 10:
            panel_w = 400
            panel_h = 400
            
        img_w, img_h = self.current_image.size
        ratio = min(panel_w / img_w, panel_h / img_h)
        
        # Scale only if the image doesn't fit or needs resizing
        new_w = max(int(img_w * ratio), 1)
        new_h = max(int(img_h * ratio), 1)
        
        resized_img = self.current_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.display_photo = ImageTk.PhotoImage(resized_img)
        self.image_display.configure(image=self.display_photo)

    def on_preview_resize(self, event):
        """Triggered on pane resizing to keep preview centered and scaled."""
        if self.current_image:
            # We delay slightly to avoid heavy computation during active dragging
            self.after(50, self.update_image_preview)

    def import_file(self):
        file_path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.tiff *.gif"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                img = Image.open(file_path)
                # Keep loaded in memory, convert to RGB if palette/RGBA for safety
                img.load()
                self.load_image(img)
                self.lbl_status.configure(text=f"已载入文件: {os.path.basename(file_path)}", text_color="gray")
            except Exception as e:
                self.lbl_status.configure(text=f"图片读取失败: {str(e)}", text_color="red")

    def import_from_clipboard(self):
        """Read image from clipboard and start OCR."""
        try:
            data = ImageGrab.grabclipboard()
            if isinstance(data, Image.Image):
                self.load_image(data)
                self.lbl_status.configure(text="成功从剪贴板读取图片", text_color="gray")
                return True
            elif isinstance(data, list) and len(data) > 0:
                filepath = data[0]
                if os.path.exists(filepath) and filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif')):
                    img = Image.open(filepath)
                    self.load_image(img)
                    self.lbl_status.configure(text=f"成功载入剪贴板文件: {os.path.basename(filepath)}", text_color="gray")
                    return True
            
            self.lbl_status.configure(text="剪贴板中未发现图片数据", text_color="orange")
        except Exception as e:
            self.lbl_status.configure(text=f"读取剪贴板异常: {str(e)}", text_color="red")
        return False

    def on_window_activate(self, event):
        """Triggered when window gets active from OS or keyboard focus."""
        # Use string representation of the widget. The root window is always "."
        if str(event.widget) != ".":
            return
        if self.auto_listener_var.get():
            # Add a brief delay to ensure clipboard is unlocked and ready
            self.after(50, self.check_and_auto_ocr)

    def poll_clipboard(self):
        """Timer loop that polls clipboard every 500ms to detect new images when focused."""
        try:
            # focus_get() returns a widget if our window is focused, else None
            if self.auto_listener_var.get() and self.focus_get() is not None:
                current_hash = self.get_clipboard_content_hash()
                if current_hash and current_hash != self.last_clipboard_hash:
                    self.last_clipboard_hash = current_hash
                    success = self.import_from_clipboard()
                    if success:
                        self.lbl_status.configure(text="[自动识别] 检测到剪贴板新内容，已启动 OCR", text_color="#10b981")
        except Exception:
            pass
        # Repeat every 500ms
        self.after(500, self.poll_clipboard)

    def get_clipboard_content_hash(self):
        """Calculate a unique identifier for clipboard image or file content."""
        try:
            data = ImageGrab.grabclipboard()
            if isinstance(data, Image.Image):
                # Hash of a 10x10 thumbnail to identify the image content uniquely
                thumb = data.resize((10, 10))
                return f"img_{data.size[0]}x{data.size[1]}_{hash(thumb.tobytes())}"
            elif isinstance(data, list) and len(data) > 0:
                filepath = data[0]
                if os.path.exists(filepath) and filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif')):
                    return f"file_{filepath}_{os.path.getmtime(filepath)}"
        except Exception:
            pass
        return None

    def check_and_auto_ocr(self):
        """Performs automatic OCR if clipboard contains a new image/file."""
        current_hash = self.get_clipboard_content_hash()
        if current_hash and current_hash != self.last_clipboard_hash:
            self.last_clipboard_hash = current_hash
            success = self.import_from_clipboard()
            if success:
                self.lbl_status.configure(text="[自动识别] 检测到剪贴板新内容，已启动 OCR", text_color="#10b981")

    # --- SCREENSHOT ROUTINES ---
    def start_screenshot(self):
        """Hide window, wait briefly, capture desktop and launch selector."""
        self.withdraw()  # Hide main window
        self.update()
        
        # Allow system animation to finish
        self.after(250, self.execute_capture)

    def execute_capture(self):
        try:
            ScreenshotSelector(self, self.on_screenshot_captured, self.on_screenshot_cancel)
        except Exception as e:
            self.deiconify()
            self.lbl_status.configure(text=f"启动截图失败: {str(e)}", text_color="red")

    def on_screenshot_captured(self, image):
        self.deiconify()  # Restore main window
        self.lift()
        self.focus_force()
        self.load_image(image)
        self.lbl_status.configure(text="截图获取成功，已载入", text_color="gray")

    def on_screenshot_cancel(self):
        self.deiconify()  # Restore main window
        self.lift()
        self.focus_force()
        self.lbl_status.configure(text="已取消截图操作", text_color="gray")

    # --- OCR WORKER AND DISPLAY ---
    def perform_ocr_thread(self, img: Image.Image):
        """Runs OCR in background thread and updates GUI with results."""
        try:
            # 1. Convert image to PNG bytes in memory
            import io
            byte_arr = io.BytesIO()
            img.save(byte_arr, format='PNG')
            image_bytes = byte_arr.getvalue()
            
            # 2. Call cross-platform OCR engine
            start_time = time.time()
            text_result = recognize_text_from_bytes(image_bytes)
            elapsed_time = time.time() - start_time
            
            # 3. Store result as lines for smart formatting
            self.raw_ocr_lines = text_result.split("\n")
            
            # 4. Safely update UI inside the main thread
            self.after(0, lambda: self.on_ocr_success(elapsed_time))
        except Exception as e:
            self.after(0, lambda: self.on_ocr_failure(str(e)))

    def on_ocr_success(self, elapsed):
        char_count = sum(len(line) for line in self.raw_ocr_lines)
        self.lbl_status.configure(
            text=f"识别完成！耗时: {elapsed:.2f}秒 | 字符数: {char_count}", 
            text_color="#10b981"
        )
        
        # Update display
        self.update_ocr_textbox_display()
        
        # Auto-copy if enabled
        if self.switch_autocopy.get() == "on":
            self.copy_to_clipboard(show_status=False)
            self.lbl_status.configure(
                text=f"识别完成并已自动复制！耗时: {elapsed:.2f}秒 | 字符数: {char_count}", 
                text_color="#10b981"
            )

    def on_ocr_failure(self, err_msg):
        self.lbl_status.configure(text=f"OCR 引擎出错: {err_msg}", text_color="red")
        self.txt_result.delete("1.0", tk.END)
        self.txt_result.insert("1.0", f"[错误] OCR 运行失败:\n{err_msg}")

    def update_ocr_textbox_display(self):
        """Updates text layout based on raw lines and paragraph merging state."""
        self.txt_result.delete("1.0", tk.END)
        
        if not self.raw_ocr_lines:
            return
            
        if self.switch_merge.get() == "on":
            # Smart paragraph merging
            merged_text = self.merge_lines_intelligently(self.raw_ocr_lines)
            self.txt_result.insert("1.0", merged_text)
        else:
            # Preserve original line breaks
            self.txt_result.insert("1.0", "\n".join(self.raw_ocr_lines))

    def merge_lines_intelligently(self, text_lines):
        """Intelligently merges lines based on language detection (Chinese vs English)."""
        clean_lines = [line.strip() for line in text_lines if line.strip()]
        if not clean_lines:
            return ""
            
        # Detect language base by checking Chinese characters proportion
        full_text = "".join(clean_lines)
        chinese_chars = sum(1 for char in full_text if '\u4e00' <= char <= '\u9fff')
        is_chinese = (chinese_chars / len(full_text)) > 0.15 if full_text else False
        
        if is_chinese:
            # Chinese merging: Join lines without spaces
            result = ""
            for line in clean_lines:
                result += line
            return result
        else:
            # English/Western merging: Join lines with spaces, handling hyphenated line-endings
            result = ""
            for line in clean_lines:
                if not result:
                    result = line
                else:
                    if result.endswith("-"):
                        result = result[:-1] + line
                    else:
                        result += " " + line
            return result

    # --- COMPONENT CONTROLS ---
    def copy_to_clipboard(self, show_status=True):
        text = self.txt_result.get("1.0", tk.END).strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            if show_status:
                self.lbl_status.configure(text="文本已复制到剪贴板！", text_color="#10b981")
        else:
            if show_status:
                self.lbl_status.configure(text="无文本内容可复制", text_color="orange")

    def save_text_file(self):
        text = self.txt_result.get("1.0", tk.END).strip()
        if not text:
            self.lbl_status.configure(text="无内容可保存", text_color="orange")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="保存识别文本",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.lbl_status.configure(text=f"文本已保存至: {os.path.basename(file_path)}", text_color="#10b981")
            except Exception as e:
                self.lbl_status.configure(text=f"保存文件失败: {str(e)}", text_color="red")

    def clear_all(self):
        self.current_image = None
        self.raw_ocr_lines = []
        self.last_clipboard_hash = None
        self.image_display.configure(image="")
        self.image_display.grid_remove()
        self.placeholder_container.grid(row=0, column=0)
        self.txt_result.delete("1.0", tk.END)
        self.lbl_status.configure(text="内容已清空", text_color="gray")


if __name__ == "__main__":
    app = LiteOcrApp()
    app.mainloop()
