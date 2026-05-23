import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cross-platform OCR Engine API
def recognize_text_from_bytes(image_bytes: bytes) -> str:
    """
    Perform OCR on the provided image bytes.
    Detects the current OS and uses the native system OCR (Windows.Media.Ocr on Windows, Vision on macOS).
    This function should be run in a separate thread to prevent blocking the GUI.
    """
    if sys.platform == "win32":
        return _run_windows_ocr(image_bytes)
    elif sys.platform == "darwin":
        return _run_macos_ocr(image_bytes)
    else:
        return "[错误] 不支持的操作系统。目前仅支持 Windows 和 macOS。"

def _run_windows_ocr(image_bytes: bytes) -> str:
    """
    Call Windows 10/11 built-in OCR engine using winrt/winsdk.
    """
    try:
        import asyncio
        # We try importing winrt or winsdk (preferring winsdk since it has stable prebuilt wheels for Python 3.12)
        try:
            import winsdk.windows.media.ocr as ocr
            import winsdk.windows.graphics.imaging as imaging
            import winsdk.windows.storage.streams as streams
            import winsdk.windows.globalization as globalization
            has_winsdk = True
        except ImportError:
            try:
                import winrt.windows.media.ocr as ocr
                import winrt.windows.graphics.imaging as imaging
                import winrt.windows.storage.streams as streams
                import winrt.windows.globalization as globalization
                has_winsdk = False
            except ImportError:
                return "[错误] 未检测到 Windows SDK 绑定。请确保在 Windows 上运行 'pip install winsdk'。"

        async def win_ocr_async(data):
            # Create InMemoryRandomAccessStream from bytes
            stream = streams.InMemoryRandomAccessStream()
            writer = streams.DataWriter(stream)
            writer.write_bytes(data)
            await writer.store_async()
            await writer.flush_async()
            stream.seek(0)
            
            # Decode the image to SoftwareBitmap
            decoder = await imaging.BitmapDecoder.create_async(stream)
            software_bitmap = await decoder.get_software_bitmap_async()
            
            # Create OCR engine
            # We try to use the system default language list, or fallback to Simplified Chinese/English
            engine = ocr.OcrEngine.try_create_from_user_profile_languages()
            if not engine:
                lang = globalization.Language("zh-Hans-CN")
                if ocr.OcrEngine.is_language_supported(lang):
                    engine = ocr.OcrEngine.try_create_from_language(lang)
                else:
                    engine = ocr.OcrEngine.try_create_from_language(globalization.Language("en-US"))
            
            if not engine:
                raise RuntimeError("无法创建 Windows OCR 引擎")
            
            # Run recognition
            ocr_result = await engine.recognize_async(software_bitmap)
            
            # Combine lines
            text_lines = []
            for line in ocr_result.lines:
                text_lines.append(line.text)
            return "\n".join(text_lines)

        # Run the async function using asyncio event loop
        # Since this is run in a worker thread, we create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(win_ocr_async(image_bytes))
            return result
        finally:
            loop.close()

    except Exception as e:
        logging.error("Windows OCR failed", exc_info=True)
        return f"[OCR 识别失败 (Windows)]: {str(e)}"

def _run_macos_ocr(image_bytes: bytes) -> str:
    """
    Call macOS native Vision text recognition framework using pyobjc.
    """
    try:
        import objc
        from Cocoa import NSData
        from Quartz import CGImageSourceCreateWithData, CGImageSourceCreateImageAtIndex
        import Vision
        
        # 1. Create CGImage from image bytes
        ns_data = NSData.dataWithBytes_length_(image_bytes, len(image_bytes))
        image_source = CGImageSourceCreateWithData(ns_data, None)
        if not image_source:
            return "[错误] 无法从数据加载图片（CGImageSource 创建失败）"
        
        cg_image = CGImageSourceCreateImageAtIndex(image_source, 0, None)
        if not cg_image:
            return "[错误] 无法获取 CGImage 实例"
            
        recognized_texts = []
        
        # 2. Define standard completion handler
        def handler(request, error):
            if error:
                logging.error(f"macOS Vision recognition error: {error}")
                return
            results = request.results()
            if results:
                for result in results:
                    candidates = result.topCandidates_(1)
                    if candidates and len(candidates) > 0:
                        recognized_texts.append(candidates[0].string())

        # 3. Create recognition request
        request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        
        # Add support for Chinese & English recognition on macOS (if supported by OS version)
        # Vision supports languages detection and specifying languages
        try:
            # Check if current OS supports specifying languages
            request.setRecognitionLanguages_(["zh-Hans", "en-US"])
        except AttributeError:
            pass  # Older macOS version, use default
            
        # 4. Perform the request using the handler
        request_handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
        success, error = request_handler.performRequests_error_([request], None)
        
        if not success:
            return f"[错误] macOS Vision 执行失败: {error}"
            
        return "\n".join(recognized_texts)
        
    except Exception as e:
        logging.error("macOS OCR failed", exc_info=True)
        return f"[OCR 识别失败 (macOS)]: {str(e)}"
