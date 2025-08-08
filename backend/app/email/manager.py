"""
E-posta işlemleri modülü
SMTP configuration, email sending ve template sistemi
"""

import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
import json
from datetime import datetime

from ..config.settings import settings
from ..config.logging import main_logger
from ..database.operations import db_manager


class EmailTemplate:
    """E-posta şablon sınıfı"""
    
    def __init__(self, name: str, subject: str, html_content: str, text_content: str = None):
        self.name = name
        self.subject = subject
        self.html_content = html_content
        self.text_content = text_content or self._html_to_text(html_content)
        self.variables = self._extract_variables()
    
    def _html_to_text(self, html_content: str) -> str:
        """HTML'yi plain text'e çevirir (basit implementation)"""
        import re
        # HTML tag'lerini kaldır
        text = re.sub('<[^<]+?>', '', html_content)
        # Çoklu boşlukları tek boşluğa çevir
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_variables(self) -> List[str]:
        """Şablondaki değişkenleri extract eder"""
        import re
        variables = set()
        
        # Jinja2 variable pattern {{ variable_name }}
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
        
        for content in [self.subject, self.html_content, self.text_content]:
            matches = re.findall(pattern, content)
            variables.update(matches)
        
        return list(variables)
    
    def render(self, variables: Dict[str, Any]) -> Dict[str, str]:
        """
        Şablonu render eder
        
        Args:
            variables: Template değişkenleri
            
        Returns:
            Dict: Render edilmiş içerik
        """
        env = Environment()
        
        # Subject render
        subject_template = env.from_string(self.subject)
        rendered_subject = subject_template.render(**variables)
        
        # HTML content render
        html_template = env.from_string(self.html_content)
        rendered_html = html_template.render(**variables)
        
        # Text content render
        text_template = env.from_string(self.text_content)
        rendered_text = text_template.render(**variables)
        
        return {
            "subject": rendered_subject,
            "html": rendered_html,
            "text": rendered_text
        }


class EmailSender:
    """E-posta gönderme sınıfı"""
    
    def __init__(self):
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.from_email = settings.email_from
        self._is_configured = self._check_configuration()
    
    def _check_configuration(self) -> bool:
        """SMTP konfigürasyonunu kontrol eder"""
        required_fields = [
            self.smtp_server,
            self.smtp_username,
            self.smtp_password,
            self.from_email
        ]
        return all(field is not None for field in required_fields)
    
    async def send_email(
        self,
        to_emails: Union[str, List[str]],
        subject: str,
        html_content: str = None,
        text_content: str = None,
        attachments: List[Dict[str, Any]] = None,
        cc_emails: List[str] = None,
        bcc_emails: List[str] = None
    ) -> Dict[str, Any]:
        """
        E-posta gönderir
        
        Args:
            to_emails: Alıcı e-posta adresleri
            subject: E-posta konusu
            html_content: HTML içerik
            text_content: Text içerik
            attachments: Ek dosyalar
            cc_emails: CC e-posta adresleri
            bcc_emails: BCC e-posta adresleri
            
        Returns:
            Dict: Gönderim sonucu
        """
        if not self._is_configured:
            return {
                "success": False,
                "error": "SMTP configuration is not complete"
            }
        
        try:
            # E-posta mesajını oluştur
            message = MIMEMultipart("alternative")
            message["From"] = self.from_email
            
            # To adresleri
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            message["To"] = ", ".join(to_emails)
            
            # CC adresleri
            if cc_emails:
                message["Cc"] = ", ".join(cc_emails)
                to_emails.extend(cc_emails)
            
            # BCC adresleri (header'a eklenmez ama gönderim listesine eklenir)
            if bcc_emails:
                to_emails.extend(bcc_emails)
            
            message["Subject"] = subject
            
            # İçerik ekle
            if text_content:
                text_part = MIMEText(text_content, "plain", "utf-8")
                message.attach(text_part)
            
            if html_content:
                html_part = MIMEText(html_content, "html", "utf-8")
                message.attach(html_part)
            
            # Ek dosyaları ekle
            if attachments:
                for attachment in attachments:
                    await self._add_attachment(message, attachment)
            
            # E-postayı gönder
            await self._send_message(message, to_emails)
            
            main_logger.info(
                "Email sent successfully",
                to_emails=to_emails,
                subject=subject,
                attachments_count=len(attachments) if attachments else 0
            )
            
            return {
                "success": True,
                "message": "Email sent successfully",
                "to_emails": to_emails,
                "sent_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            main_logger.error(
                "Failed to send email",
                error=str(e),
                to_emails=to_emails,
                subject=subject
            )
            
            return {
                "success": False,
                "error": str(e),
                "to_emails": to_emails
            }
    
    async def _add_attachment(self, message: MIMEMultipart, attachment: Dict[str, Any]):
        """
        Mesaja ek dosya ekler
        
        Args:
            message: E-posta mesajı
            attachment: Ek dosya bilgileri (filename, content veya filepath)
        """
        filename = attachment.get("filename")
        content = attachment.get("content")
        filepath = attachment.get("filepath")
        
        if filepath and Path(filepath).exists():
            with open(filepath, "rb") as f:
                content = f.read()
                if not filename:
                    filename = Path(filepath).name
        
        if content and filename:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename= "{filename}"'
            )
            message.attach(part)
    
    async def _send_message(self, message: MIMEMultipart, to_emails: List[str]):
        """
        SMTP üzerinden mesaj gönderir
        
        Args:
            message: E-posta mesajı
            to_emails: Alıcı e-posta adresleri
        """
        # SMTP bağlantısı kur
        if self.smtp_use_tls:
            smtp = aiosmtplib.SMTP(hostname=self.smtp_server, port=self.smtp_port, use_tls=True)
        else:
            smtp = aiosmtplib.SMTP(hostname=self.smtp_server, port=self.smtp_port)
        
        await smtp.connect()
        
        # Kimlik doğrulama
        if self.smtp_username and self.smtp_password:
            await smtp.login(self.smtp_username, self.smtp_password)
        
        # E-postayı gönder
        await smtp.send_message(message, recipients=to_emails)
        
        # Bağlantıyı kapat
        await smtp.quit()
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        SMTP bağlantısını test eder
        
        Returns:
            Dict: Test sonucu
        """
        if not self._is_configured:
            return {
                "success": False,
                "error": "SMTP configuration is not complete"
            }
        
        try:
            # SMTP bağlantısı test et
            if self.smtp_use_tls:
                smtp = aiosmtplib.SMTP(hostname=self.smtp_server, port=self.smtp_port, use_tls=True)
            else:
                smtp = aiosmtplib.SMTP(hostname=self.smtp_server, port=self.smtp_port)
            
            await smtp.connect()
            
            # Kimlik doğrulama test et
            if self.smtp_username and self.smtp_password:
                await smtp.login(self.smtp_username, self.smtp_password)
            
            await smtp.quit()
            
            return {
                "success": True,
                "message": "SMTP connection successful"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class EmailManager:
    """Ana e-posta yönetim sınıfı"""
    
    def __init__(self):
        self.sender = EmailSender()
        self.templates: Dict[str, EmailTemplate] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """Default e-posta şablonlarını yükler"""
        # Scraping başlama bildirimi
        scraping_started_template = EmailTemplate(
            name="scraping_started",
            subject="VeriSnap - Scraping İşlemi Başladı",
            html_content="""
            <h2>Scraping İşlemi Başladı</h2>
            <p>Merhaba,</p>
            <p><strong>{{ target_site }}</strong> için scraping işleminiz başlamıştır.</p>
            <p><strong>Detaylar:</strong></p>
            <ul>
                <li>Session ID: {{ session_id }}</li>
                <li>Hedef Site: {{ target_site }}</li>
                <li>Başlangıç URL: {{ start_url }}</li>
                <li>Maksimum Sayfa: {{ max_pages }}</li>
                <li>Başlama Zamanı: {{ started_at }}</li>
            </ul>
            <p>İşlem tamamlandığında bilgilendirileceksiniz.</p>
            <p>İyi çalışmalar,<br>VeriSnap Ekibi</p>
            """
        )
        
        # Scraping tamamlanma bildirimi
        scraping_completed_template = EmailTemplate(
            name="scraping_completed",
            subject="VeriSnap - Scraping İşlemi Tamamlandı",
            html_content="""
            <h2>Scraping İşlemi Tamamlandı</h2>
            <p>Merhaba,</p>
            <p><strong>{{ target_site }}</strong> için scraping işleminiz başarıyla tamamlanmıştır.</p>
            <p><strong>Sonuçlar:</strong></p>
            <ul>
                <li>Session ID: {{ session_id }}</li>
                <li>Toplanan Kayıt Sayısı: {{ total_records }}</li>
                <li>Scraping Yapılan Sayfa: {{ pages_scraped }}</li>
                <li>Başarı Oranı: {{ success_rate }}%</li>
                <li>Tamamlanma Zamanı: {{ completed_at }}</li>
                <li>Toplam Süre: {{ duration }}</li>
            </ul>
            <p>Verilerinizi panelden indirebilirsiniz.</p>
            <p>İyi çalışmalar,<br>VeriSnap Ekibi</p>
            """
        )
        
        # Scraping hata bildirimi
        scraping_error_template = EmailTemplate(
            name="scraping_error",
            subject="VeriSnap - Scraping İşleminde Hata",
            html_content="""
            <h2>Scraping İşleminde Hata Oluştu</h2>
            <p>Merhaba,</p>
            <p><strong>{{ target_site }}</strong> için scraping işleminizde hata oluşmuştur.</p>
            <p><strong>Hata Detayları:</strong></p>
            <ul>
                <li>Session ID: {{ session_id }}</li>
                <li>Hata Zamanı: {{ error_time }}</li>
                <li>Hata Mesajı: {{ error_message }}</li>
                <li>Toplanan Kayıt Sayısı: {{ total_records }}</li>
            </ul>
            <p>Lütfen ayarlarınızı kontrol edip tekrar deneyiniz.</p>
            <p>İyi çalışmalar,<br>VeriSnap Ekibi</p>
            """
        )
        
        self.templates["scraping_started"] = scraping_started_template
        self.templates["scraping_completed"] = scraping_completed_template
        self.templates["scraping_error"] = scraping_error_template
    
    async def send_template_email(
        self,
        template_name: str,
        to_emails: Union[str, List[str]],
        variables: Dict[str, Any],
        attachments: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Şablon kullanarak e-posta gönderir
        
        Args:
            template_name: Şablon adı
            to_emails: Alıcı e-posta adresleri
            variables: Şablon değişkenleri
            attachments: Ek dosyalar
            
        Returns:
            Dict: Gönderim sonucu
        """
        if template_name not in self.templates:
            return {
                "success": False,
                "error": f"Template '{template_name}' not found"
            }
        
        template = self.templates[template_name]
        rendered = template.render(variables)
        
        return await self.sender.send_email(
            to_emails=to_emails,
            subject=rendered["subject"],
            html_content=rendered["html"],
            text_content=rendered["text"],
            attachments=attachments
        )
    
    async def send_scraping_notification(
        self,
        notification_type: str,
        user_email: str,
        session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Scraping bildirimi gönderir
        
        Args:
            notification_type: Bildirim tipi (started, completed, error)
            user_email: Kullanıcı e-posta adresi
            session_data: Session verileri
            
        Returns:
            Dict: Gönderim sonucu
        """
        template_name = f"scraping_{notification_type}"
        
        return await self.send_template_email(
            template_name=template_name,
            to_emails=user_email,
            variables=session_data
        )
    
    def add_template(self, template: EmailTemplate):
        """
        Yeni şablon ekler
        
        Args:
            template: E-posta şablonu
        """
        self.templates[template.name] = template
        main_logger.info(f"Email template '{template.name}' added")
    
    def get_template(self, name: str) -> Optional[EmailTemplate]:
        """
        Şablon getirir
        
        Args:
            name: Şablon adı
            
        Returns:
            Optional[EmailTemplate]: Şablon objesi
        """
        return self.templates.get(name)
    
    def list_templates(self) -> List[str]:
        """
        Şablon listesi döndürür
        
        Returns:
            List[str]: Şablon adları
        """
        return list(self.templates.keys())
    
    async def test_email_configuration(self) -> Dict[str, Any]:
        """
        E-posta konfigürasyonunu test eder
        
        Returns:
            Dict: Test sonucu
        """
        return await self.sender.test_connection()


# Global email manager instance
email_manager = EmailManager()