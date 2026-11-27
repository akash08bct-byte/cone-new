"""Preview and save the bundled invoice PDF."""

from pathlib import Path

from PyQt5.QtCore import QIODevice, QSaveFile, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from paths import INVOICE_PDF


class InvoicePreview(QGraphicsView):
    def __init__(self, zoom_by, parent=None):
        super().__init__(parent)
        self.zoom_by = zoom_by
        self.setScene(QGraphicsScene(self))
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta and self.scene().items():
            self.zoom_by(1.2 ** (delta / 120))
            event.accept()
        else:
            super().wheelEvent(event)

    def load_pdf(self, path):
        import pypdfium2 as pdfium

        page_top = 0
        document = pdfium.PdfDocument(path)
        try:
            for page in document:
                try:
                    bitmap = page.render(
                        scale=2, rev_byteorder=True,
                        force_bitmap_format=pdfium.raw.FPDFBitmap_BGR,
                    )
                    try:
                        image = QImage(
                            bytes(bitmap.buffer), bitmap.width, bitmap.height,
                            bitmap.stride, QImage.Format_RGB888,
                        )
                        pixmap = QPixmap.fromImage(image)
                    finally:
                        bitmap.close()
                finally:
                    page.close()

                item = self.scene().addPixmap(pixmap)
                item.setTransformationMode(Qt.SmoothTransformation)
                item.setScale(0.5)
                item.setPos(-pixmap.width() / 4, page_top)
                page_top += pixmap.height() / 2 + 12
        finally:
            document.close()


class InvoiceViewer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Invoice Preview")
        self.resize(960, 860)

        self.zoom = 1.0
        self.preview = InvoicePreview(self.zoom_by, self)

        self.status_lbl = QLabel("Loading invoice...")
        self.download_btn = QPushButton("Download PDF")
        self.download_btn.clicked.connect(self.download_pdf)
        self.zoom_out_btn = QPushButton("Zoom Out")
        self.zoom_out_btn.clicked.connect(lambda: self.zoom_by(1 / 1.2))
        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_in_btn.clicked.connect(lambda: self.zoom_by(1.2))
        self.zoom_reset_btn = QPushButton("Reset")
        self.zoom_reset_btn.clicked.connect(lambda: self.set_zoom(1.0))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Invoice Preview"))
        toolbar.addStretch()
        toolbar.addWidget(self.status_lbl)
        for button in (self.zoom_out_btn, self.zoom_in_btn, self.zoom_reset_btn):
            button.setEnabled(False)
            toolbar.addWidget(button)
        toolbar.addWidget(self.download_btn)
        toolbar.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.preview)

        exists = INVOICE_PDF.is_file()
        self.download_btn.setEnabled(exists)
        if not exists:
            self.status_lbl.setText("Invoice PDF is missing")
            return

        try:
            self.preview.load_pdf(INVOICE_PDF)
        except ImportError:
            self.status_lbl.setText("Install pypdfium2 to preview the invoice")
            return
        except Exception as error:
            self.preview.scene().clear()
            self.status_lbl.setText(f"Could not preview invoice: {error}")
            return
        self.set_zoom(1.0)

    def zoom_by(self, multiplier):
        self.set_zoom(self.zoom * multiplier)

    def set_zoom(self, factor):
        factor = max(0.5, min(3.0, round(factor, 2)))
        self.preview.scale(factor / self.zoom, factor / self.zoom)
        self.zoom = factor
        self.status_lbl.setText(f"{factor:.0%}")
        self.zoom_out_btn.setEnabled(factor > 0.5)
        self.zoom_in_btn.setEnabled(factor < 3.0)
        self.zoom_reset_btn.setEnabled(factor != 1.0)

    def download_pdf(self):
        dialog = QFileDialog(self, "Save Invoice as PDF")
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setNameFilter("PDF Files (*.pdf)")
        dialog.setDefaultSuffix("pdf")
        dialog.selectFile(INVOICE_PDF.name)
        if dialog.exec_():
            self.save_pdf(dialog.selectedFiles()[0])

    def save_pdf(self, path):
        try:
            data = INVOICE_PDF.read_bytes()
        except OSError as error:
            self.status_lbl.setText(f"Could not read invoice PDF: {error}")
            return

        output = QSaveFile(path)
        if not output.open(QIODevice.WriteOnly):
            self.status_lbl.setText(f"Save failed: {output.errorString()}")
            return
        if output.write(data) != len(data) or not output.commit():
            self.status_lbl.setText(f"Save failed: {output.errorString()}")
            return

        self.status_lbl.setText(f"Saved: {Path(path).name}")
