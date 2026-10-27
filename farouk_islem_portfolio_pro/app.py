import hmac
import os
import smtplib
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, redirect, render_template, request, session,
    url_for,
)
from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, HiddenField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import AnyOf, DataRequired, Email, Length, Optional

load_dotenv()
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY") or "dev-only-change-before-deploy",
    MAX_CONTENT_LENGTH=64 * 1024,
    WTF_CSRF_TIME_LIMIT=3600,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
)

SUPPORTED_LANGUAGES = ("ar", "en")

TEXT = {
    "ar": {
        "page_title": "فاروق إسلام | تطوير مواقع وتطبيقات ويب",
        "meta_description": "فاروق إسلام، مطوّر ويب من الجزائر. أساعد الأفراد والأنشطة التجارية على بناء مواقع واضحة وسهلة الاستخدام وتطوير تطبيقات ويب عملية.",
        "skip": "انتقل إلى المحتوى",
        "nav_label": "التنقل الرئيسي",
        "nav_services": "الخدمات", "nav_projects": "المشاريع", "nav_feedback": "الآراء", "nav_about": "نبذة عني", "nav_contact": "لنتحدث عن مشروعك",
        "switch_language": "English", "switch_theme_dark": "التبديل إلى الوضع الفاتح", "switch_theme_light": "التبديل إلى الوضع الداكن",
        "open_menu": "فتح القائمة", "close_menu": "إغلاق القائمة",
        "available": "متاح لمشاريع العمل الحر", "hello": "مرحبًا، أنا", "hero_line1": "مواقع واضحة الفكرة،", "hero_line2": "ومصمّمة لتخدم هدفك.",
        "hero_description": "أطوّر مواقع وتطبيقات ويب تجمع بين عرض واضح للمعلومات، وتجربة مريحة على الهاتف والحاسوب، ووظائف تخدم احتياج مشروعك.",
        "hero_contact": "لديك مشروع؟ لنتحدث", "hero_projects": "استكشف أعمالي", "hero_item1": "مواقع شخصية وتجارية", "hero_item2": "تطبيقات ويب", "hero_item3": "أدوات رقمية",
        "chip1_title": "تجربة استخدام", "chip1_sub": "واضحة وسلسة", "chip2_title": "تطوير ويب", "chip2_sub": "من الفكرة إلى الإطلاق",
        "values_label": "مبادئ العمل", "values_intro": "كل مشروع يبدأ بهدف واضح", "value1": "تصميم متجاوب", "value2": "تواصل مباشر", "value3": "اهتمام بالتفاصيل", "value4": "أداء وتجربة سلسة",
        "services_index": "01 / الخدمات", "services_title1": "خدمات ويب", "services_title2": "تناسب احتياج مشروعك.", "services_intro": "سواء كنت تبدأ من الصفر أو تطوّر موقعًا قائمًا، اشرح لي ما تحتاج إليه لنحدّد نطاقًا واقعيًا وخطوات تنفيذ واضحة.",
        "projects_index": "02 / أعمال مختارة", "projects_title1": "مشاريع يمكنك", "projects_title2": "استكشافها بنفسك.", "projects_intro": "تصفّح المشاريع، وجرّب النسخة الحية عندما تكون متاحة، أو راجع المستودع للاطلاع على الكود والتقنيات المستخدمة.",
        "project_live": "تجربة الموقع", "project_code": "الكود المصدري", "project_live_missing": "المعاينة غير متاحة بعد", "project_code_missing": "الكود غير منشور بعد", "more_projects": "عرض المزيد من المشاريع", "less_projects": "عرض مشاريع أقل", "project_no_links": "تفاصيل إضافية غير متاحة حاليًا",
        "process_index": "03 / طريقة العمل", "process_title1": "خطوات عمل", "process_title2": "واضحة من البداية.", "process_intro": "أتفق معك على الهدف والوظائف المطلوبة قبل بدء التطوير، مع توضيح نطاق العمل وما يشمله التسليم.",
        "step1_title": "نفهم الهدف", "step1_text": "نبدأ بما تريد أن يحققه المشروع، ومن سيستخدمه، وما أهم الوظائف المطلوبة.", "step2_title": "نبني الحل", "step2_text": "أطوّر الواجهة والوظائف المتفق عليها مع مشاركة التحديثات المهمة أثناء العمل.", "step3_title": "نراجع ونسلّم", "step3_text": "نختبر الأساسيات، نراجع الملاحظات ضمن نطاق المشروع، ثم نجهّز التسليم أو النشر.",
        "feedback_index": "04 / آراء الزوار", "feedback_title1": "شارك تجربتك", "feedback_title2": "وساعدني على التطوّر.", "feedback_intro": "إذا استخدمت الموقع أو تعاملت معي في مشروع، يمكنك مشاركة رأيك بصدق. تُراجع المشاركات قبل النشر، ولا تُعرض إلا بعد الموافقة عليها.",
        "feedback_empty_title": "لا توجد آراء منشورة بعد", "feedback_empty_text": "لم تُنشر آراء بعد. بعد وصول المشاركات ومراجعتها، ستظهر هنا التقييمات والتعليقات التي وافق أصحابها على نشرها.",
        "feedback_count": "تقييم منشور", "feedback_count_plural": "تقييمات منشورة", "feedback_avg": "متوسط التقييم", "feedback_form_title": "شارك تجربتك", "feedback_form_intro": "اختر تقييمًا، ويمكنك إضافة تعليق إن رغبت. تُراجع المشاركات قبل نشرها.",
        "feedback_name": "اسمك (اختياري)", "feedback_name_placeholder": "الاسم الذي تفضّل عرضه", "feedback_rating": "تقييمك", "feedback_rating_hint": "1 = يحتاج إلى تحسين · 5 = ممتاز", "feedback_comment": "تعليقك (اختياري)", "feedback_comment_placeholder": "ما الذي أعجبك أو ما الذي يمكن تحسينه؟", "feedback_consent": "أوافق على النشر بعد المراجعة.", "feedback_submit": "إرسال التقييم", "feedback_privacy": "لا تضف معلومات خاصة.",
        "support_button": "مساندة المطوّر",
        "about_index": "05 / نبذة عني", "about_title1": "تطوير عملي،", "about_title2": "وتجربة سهلة الاستخدام.", "about_text2": "أهتم بأن يكون الموقع مفهومًا وسهل التصفح، وأن تعمل عناصره كما يتوقع المستخدم. لذلك أوازن بين شكل الواجهة، وتنظيم المحتوى، والوظائف التي يحتاجها المشروع.", "about_github": "اطّلع على مشاريعي في GitHub",
        "faq_index": "06 / أسئلة شائعة", "faq_title1": "قبل أن", "faq_title2": "نبدأ.", "faq_intro": "إجابات مختصرة تساعدك على معرفة الخطوة التالية.",
        "faq1_q": "كيف أبدأ طلب مشروع؟", "faq1_a": "أرسل وصفًا موجزًا للهدف والوظائف الأساسية والموعد المتوقع إن وُجد. بعد مراجعة التفاصيل نحدّد نطاقًا واضحًا للخطوات والتسليم.",
        "faq2_q": "كم يستغرق التنفيذ؟", "faq2_a": "يعتمد ذلك على حجم المشروع وعدد الصفحات والوظائف وجاهزية المحتوى. يمكن تحديد تقدير واقعي بعد فهم المتطلبات.",
        "faq3_q": "هل يمكن تحسين موقع قائم؟", "faq3_a": "نعم، يمكن مراجعة تجربة الهاتف، وتنظيم المحتوى، ومعالجة مشكلات الواجهة أو تطوير وظائف محددة بحسب حالة الموقع.",
        "faq4_q": "هل يمكن إضافة ميزات الذكاء الاصطناعي إلى الموقع؟", "faq4_a": "نعم، يمكن دمج خدمات الذكاء الاصطناعي عبر واجهات API بحسب احتياجات المشروع، مثل المساعدات الذكية أو معالجة النصوص. نحدّد الوظيفة المناسبة ومتطلباتها قبل التنفيذ.",
        "contact_index": "07 / التواصل", "contact_title1": "تخطّط لموقع؟", "contact_title2": "لنناقش ما تحتاج إليه.", "contact_intro": "أرسل وصفًا مختصرًا لفكرتك أو للمشكلة التي تريد حلّها. سأراجع التفاصيل ونناقش نطاق العمل والخطوة المناسبة التالية.",
        "email_label": "البريد الإلكتروني", "direct_message": "رسالة مباشرة", "whatsapp_label": "تواصل عبر WhatsApp", "privacy_note": "تُستخدم بيانات نموذج التواصل للرد على استفسارك فقط، ولا تُعرض علنًا.",
        "contact_form_title": "أخبرني عن مشروعك", "required_note": "الحقول المعلّمة بـ * مطلوبة.", "name": "اسمك", "name_placeholder": "كيف أناديك؟", "email": "بريدك الإلكتروني", "service": "ما الخدمة التي تحتاجها؟", "service_placeholder": "مثلًا: موقع تعريفي لنشاطي", "message": "تفاصيل المشروع", "message_placeholder": "ما الذي تريد بناءه؟ وما أهم نتيجة تتوقعها؟", "message_help": "لا تحتاج إلى كتابة كل التفاصيل الآن.", "submit_contact": "إرسال طلب المشروع", "contact_fallback": "إذا تعذّر إرسال النموذج، يمكنك التواصل مباشرة عبر البريد أو WhatsApp.",
        "footer_tagline": "تطوير مواقع وتطبيقات ويب باهتمام بالتفاصيل.", "close_notice": "إغلاق الرسالة", "rating_one": "تقييم واحد", "rating_many": "تقييمات", "admin_title": "إدارة الآراء", "admin_login": "دخول الإدارة", "admin_password": "كلمة مرور الإدارة", "admin_login_button": "دخول", "admin_unconfigured": "إدارة الآراء غير مفعّلة بعد. اضبط FEEDBACK_ADMIN_PASSWORD في متغيرات البيئة.", "admin_pending": "مشاركات تنتظر المراجعة", "admin_approve": "اعتماد ونشر", "admin_reject": "رفض", "admin_logout": "تسجيل الخروج", "admin_no_pending": "لا توجد مشاركات تنتظر المراجعة.", "review_label": "تقييم", "review_submitted": "وصل تقييمك، وسيُراجع قبل نشره. شكرًا لمشاركة رأيك.", "review_validation": "اختر تقييمًا صحيحًا وتأكد من الحقول ثم أعد الإرسال.", "review_spam": "تعذّر معالجة المشاركة.", "review_saved": "تم تحديث حالة المشاركة.", "admin_bad_password": "كلمة المرور غير صحيحة.", "contact_success": "وصل طلبك بنجاح. سأراجع التفاصيل وأرد عليك عبر بريدك.", "contact_disabled": "نموذج الرسائل غير مفعّل بعد. يمكنك مراسلتي مباشرة عبر البريد أو WhatsApp.", "contact_failed": "لم يتم إرسال الرسالة الآن. استخدم البريد أو WhatsApp للتواصل مباشرة.", "contact_invalid": "تحقّق من الحقول المطلوبة ثم أعد الإرسال.", "contact_spam": "تعذّر معالجة الطلب. جرّب التواصل عبر البريد الإلكتروني.", "request_too_large": "حجم الطلب أكبر من المسموح به.",
    },
    "en": {
        "page_title": "Farouk Islem | Websites & Web Applications",
        "meta_description": "Farouk Islem is a web developer based in Algeria, building clear, responsive websites and practical web applications for individuals and businesses.",
        "skip": "Skip to content", "nav_label": "Main navigation", "nav_services": "Services", "nav_projects": "Projects", "nav_feedback": "Feedback", "nav_about": "About", "nav_contact": "Let’s discuss your project",
        "switch_language": "العربية", "switch_theme_dark": "Switch to light mode", "switch_theme_light": "Switch to dark mode", "open_menu": "Open menu", "close_menu": "Close menu",
        "available": "Open to freelance projects", "hello": "Hello, I’m", "hero_line1": "Websites with a clear purpose,", "hero_line2": "built around your goals.",
        "hero_description": "I build websites and web applications with clear information, a comfortable experience across devices, and features shaped around your project’s needs.",
        "hero_contact": "Have a project? Let’s talk", "hero_projects": "Explore my work", "hero_item1": "Personal & business sites", "hero_item2": "Web applications", "hero_item3": "Digital tools",
        "chip1_title": "User experience", "chip1_sub": "Clear and intuitive", "chip2_title": "Web development", "chip2_sub": "From idea to launch",
        "values_label": "Working principles", "values_intro": "Every project starts with a clear goal", "value1": "Responsive design", "value2": "Direct communication", "value3": "Attention to detail", "value4": "Smooth performance",
        "services_index": "01 / SERVICES", "services_title1": "Web development", "services_title2": "for your project’s needs.", "services_intro": "Whether you are starting from scratch or improving an existing site, tell me what you need and we can define a practical scope and clear next steps.",
        "projects_index": "02 / SELECTED WORK", "projects_title1": "Projects you can", "projects_title2": "explore for yourself.", "projects_intro": "Explore each project, try the live version when available, or open its repository to review the code and technologies used.",
        "project_live": "Live demo", "project_code": "Source code", "project_live_missing": "Preview not available yet", "project_code_missing": "Source not published yet", "more_projects": "Show more projects", "less_projects": "Show fewer projects", "project_no_links": "More details are not available yet",
        "process_index": "03 / PROCESS", "process_title1": "A clear process,", "process_title2": "from the start.", "process_intro": "We agree on the goal and essential features before development begins, including the scope of work and what will be delivered.",
        "step1_title": "Understand the goal", "step1_text": "We start with what the project should achieve, who will use it, and which features matter most.", "step2_title": "Build the solution", "step2_text": "I develop the agreed interface and functionality, sharing meaningful progress along the way.", "step3_title": "Review and deliver", "step3_text": "We test the core features, review agreed changes, and prepare the handoff or deployment.",
        "feedback_index": "04 / FEEDBACK", "feedback_title1": "Share your experience", "feedback_title2": "and help me improve.", "feedback_intro": "If you have used this site or worked with me on a project, you can share an honest review. Submissions are reviewed before anything is published.",
        "feedback_empty_title": "No written reviews published yet", "feedback_empty_text": "No reviews have been published yet. Once submissions are reviewed, approved ratings and comments will appear here with the authors’ permission.",
        "feedback_count": "published review", "feedback_count_plural": "published reviews", "feedback_avg": "Average rating", "feedback_form_title": "Share your experience", "feedback_form_intro": "Choose a rating and add a comment if you wish. Submissions are reviewed before publication.",
        "feedback_name": "Your name (optional)", "feedback_name_placeholder": "Name you would like displayed", "feedback_rating": "Your rating", "feedback_rating_hint": "1 = needs work · 5 = excellent", "feedback_comment": "Your comment (optional)", "feedback_comment_placeholder": "What worked well, or what could be improved?", "feedback_consent": "I agree to publication after review.", "feedback_submit": "Submit feedback", "feedback_privacy": "Please leave out private details.",
        "support_button": "Supporting the developer",
        "about_index": "05 / ABOUT", "about_title1": "Practical development,", "about_title2": "thoughtful user experience.", "about_text2": "I care about making websites understandable and easy to navigate, with features that behave as users expect. That means balancing interface design, content structure, and the functionality a project actually needs.", "about_github": "Explore my projects on GitHub",
        "faq_index": "06 / FAQ", "faq_title1": "Before we", "faq_title2": "get started.", "faq_intro": "A few quick answers to help you choose the next step.",
        "faq1_q": "How do I start a project enquiry?", "faq1_a": "Share a brief description of the goal, core features, and preferred timeline if you have one. After reviewing the details, we can define the scope and delivery steps.",
        "faq2_q": "How long does development take?", "faq2_a": "Timing depends on the project's size, pages, functionality, and how ready the content is. I can provide a realistic estimate once the requirements are clear.",
        "faq3_q": "Can you improve an existing website?", "faq3_a": "Yes. We can review the mobile experience, content structure, interface issues, or specific features based on the current site.",
        "faq4_q": "Can AI features be added to a website?", "faq4_a": "Yes. AI services can be integrated through APIs when they fit the project’s needs, such as smart assistants or text processing. We define the right feature and its requirements before development.",
        "contact_index": "07 / CONTACT", "contact_title1": "Planning a website?", "contact_title2": "Let’s discuss what you need.", "contact_intro": "Send a short description of your idea or the problem you want to solve. I’ll review the details so we can discuss the scope and a sensible next step.",
        "email_label": "Email", "direct_message": "Direct message", "whatsapp_label": "Message on WhatsApp", "privacy_note": "Contact details are used only to reply to your enquiry and are not displayed publicly.",
        "contact_form_title": "Tell me about your project", "required_note": "Fields marked * are required.", "name": "Your name", "name_placeholder": "What should I call you?", "email": "Email address", "service": "What do you need?", "service_placeholder": "For example: a website for my business", "message": "Project details", "message_placeholder": "What would you like to build, and what should it achieve?", "message_help": "You do not need to have every detail figured out yet.", "submit_contact": "Send project enquiry", "contact_fallback": "If the form does not send, contact me directly by email or WhatsApp.",
        "footer_tagline": "Websites and applications built with care and clarity.", "close_notice": "Dismiss message", "rating_one": "review", "rating_many": "reviews", "admin_title": "Feedback moderation", "admin_login": "Admin sign in", "admin_password": "Admin password", "admin_login_button": "Sign in", "admin_unconfigured": "Feedback moderation is not enabled. Set FEEDBACK_ADMIN_PASSWORD in environment variables.", "admin_pending": "Submissions awaiting review", "admin_approve": "Approve & publish", "admin_reject": "Reject", "admin_logout": "Sign out", "admin_no_pending": "There are no submissions waiting for review.", "review_label": "Rating", "review_submitted": "Your rating was received and will be reviewed before publication. Thank you for sharing.", "review_validation": "Choose a valid rating and check the required fields.", "review_spam": "This submission could not be processed.", "review_saved": "Submission status updated.", "admin_bad_password": "The password is incorrect.", "contact_success": "Your enquiry was sent. I’ll review the details and reply by email.", "contact_disabled": "The message form is not configured yet. Please email or message me on WhatsApp directly.", "contact_failed": "The message could not be sent. Please contact me directly by email or WhatsApp.", "contact_invalid": "Please check the required fields and try again.", "contact_spam": "This request could not be processed. Please contact me by email.", "request_too_large": "The request is larger than allowed.",
    },
}

PROFILE = {
    "name": "Farouk Islem",
    "name_ar": "فاروق إسلام",
    "role_ar": "مطوّر ويب ومهتم بالذكاء الاصطناعي",
    "role_en": "Web Developer · AI",
    "location_ar": "الجزائر",
    "location_en": "Algeria",
    "email": os.getenv("CONTACT_EMAIL", "islemislem5560@gmail.com"),
    "intro_ar": "أطوّر مواقع وتجارب ويب تساعدك على عرض خدماتك بوضوح، وتمنح زوارك طريقة سهلة لفهم ما تقدّمه واتخاذ الخطوة التالية.",
    "intro_en": "I build websites and web experiences that present your services clearly, help visitors understand your offer, and make the next step easy.",
    "about_ar": "أطوّر مواقع وتطبيقات ويب تركّز على وضوح المحتوى وسهولة الاستخدام على مختلف الشاشات. أستخدم Python وتقنيات الويب لبناء وظائف عملية، وأدمج خدمات الذكاء الاصطناعي عندما تخدم هدف المشروع وتضيف فائدة واضحة للمستخدم.",
    "about_en": "I build websites and web applications with clear content and usability across screen sizes. I use Python and web technologies to deliver practical functionality, integrating AI services when they serve the project’s goals and provide clear value to users.",
    "github": "https://github.com/payoneerislem-cyber/Web-projects",
    "linkedin": os.getenv("LINKEDIN_URL", ""),
    "instagram": "https://www.instagram.com/faroukisslem/",
    "whatsapp": "https://wa.me/213779985001",
}

SERVICES = [
    {"number": "01", "icon": "↗", "title_ar": "مواقع شخصية ومعارض أعمال", "title_en": "Personal sites & portfolios", "description_ar": "موقع يعرّف بك وبخدماتك ويجمع أعمالك وروابطك في مساحة يسهل تصفّحها.", "description_en": "A focused website that introduces you, presents your services, and brings your work and key links together.", "deliverables_ar": ["تصميم متجاوب للهاتف والحاسوب", "عرض المشاريع والخدمات", "روابط تواصل واضحة"], "deliverables_en": ["Responsive mobile and desktop layout", "Clear project and service presentation", "Direct contact paths"]},
    {"number": "02", "icon": "▦", "title_ar": "مواقع للأنشطة التجارية", "title_en": "Business websites", "description_ar": "واجهة تساعد نشاطك على شرح ما يقدّمه والإجابة عن أسئلة العميل قبل التواصل.", "description_en": "A professional presence that explains your offer and answers key questions before a customer gets in touch.", "deliverables_ar": ["صفحات خدمات منظمة", "دعوات واضحة للتواصل", "أساسيات الظهور في البحث"], "deliverables_en": ["Structured service pages", "Clear calls to action", "Search-friendly foundations"]},
    {"number": "03", "icon": "⌘", "title_ar": "تطبيقات ويب وأتمتة بسيطة", "title_en": "Web apps & simple automation", "description_ar": "أدوات رقمية مخصصة لتقليل الأعمال المتكررة وتنظيم سير العمل حسب الاحتياج.", "description_en": "Purpose-built tools that reduce repetitive work and bring structure to a workflow.", "deliverables_ar": ["تحديد نطاق العمل أولًا", "تطوير Python وFlask عند الملاءمة", "اختبار الوظائف الأساسية"], "deliverables_en": ["Clear scope before development", "Python and Flask where suitable", "Core functionality testing"]},
    {"number": "04", "icon": "✳", "title_ar": "تحسين واجهات موجودة", "title_en": "Website UI improvements", "description_ar": "تحسين قابلية الاستخدام والتنسيق وجعل التجربة أوضح على الشاشات المختلفة.", "description_en": "Improve usability, layout consistency, and the experience across different screen sizes.", "deliverables_ar": ["مراجعة الواجهة الحالية", "تحسين العرض على الهاتف", "تنظيم المحتوى والتنقل"], "deliverables_en": ["Review of the current interface", "Mobile layout improvements", "Clearer content and navigation"]},
]

PROJECTS = [
    {
        "title": "Lumina", "category_ar": "متجر إلكتروني", "category_en": "E-commerce Website",
        "description_ar": "متجر إلكتروني يعرض المنتجات بوضوح ويوفّر تجربة تسوّق سلسة.",
        "description_en": "An e-commerce website showcasing products clearly and delivering a seamless shopping experience.",
        "stack": ["HTML/CSS", "JavaScript", "Python"],
        "live_url": "https://lumina-app-3zje.onrender.com/", "source_url": "https://github.com/payoneerislem-cyber/Web-projects",
        "visual": "lumina", "alt_ar": "معاينة واجهة مشروع Lumina", "alt_en": "Interface preview for the Lumina project",
    },
    {
        "title": "MADAR Services", "category_ar": "موقع خدمات", "category_en": "Business website",
        "description_ar": "موقع تعريفي للخدمات، صُمّم لعرض المعلومات بطريقة واضحة وسهلة التصفح.",
        "description_en": "A services website designed to present information clearly and make it easy to browse.",
        "stack": ["HTML/CSS", "JavaScript", "Python"],
        # Paste the MADAR live website URL between the quotes below.
        "live_url": "https://portfolio-project-7py3.onrender.com", "source_url": "https://github.com/payoneerislem-cyber/Web-projects/tree/main/portfolio_two_web_projects/madar-services",
        "visual": "madar", "icon": "M", "alt_ar": "أيقونة مشروع MADAR Services", "alt_en": "MADAR Services project icon",
    },
    {
        "title": "NOOR Studio", "category_ar": "موقع حجز", "category_en": "Booking website",
        "description_ar": "موقع لحجز المواعيد يعرض الخدمات ويسهّل على الزائر استكشافها.",
        "description_en": "A booking website that presents services and helps visitors explore available options.",
        "stack": ["Python", "Flask", "SQLite"],
        # Paste the NOOR Studio live website URL between the quotes below.
        "live_url": "https://portfolio-project1-9iy1.onrender.com", "source_url": "https://github.com/payoneerislem-cyber/Web-projects/tree/main/portfolio_two_web_projects/noor-booking",
        "visual": "noor", "icon": "N", "alt_ar": "أيقونة مشروع NOOR Studio", "alt_en": "NOOR Studio project icon",
    },
]
INITIAL_PROJECT_COUNT = 3

# A configurable payment link is required for real contributions. No payment destination is invented.
_candidate_support_url = os.getenv("SUPPORT_URL", "").strip()
SUPPORT_URL = _candidate_support_url if urlparse(_candidate_support_url).scheme == "https" and urlparse(_candidate_support_url).netloc else ""
DATABASE_PATH = os.getenv("PORTFOLIO_DB_PATH") or str(Path(app.instance_path) / "portfolio.sqlite3")


def current_language():
    saved = request.cookies.get("site_lang", "").lower()
    if saved in SUPPORTED_LANGUAGES:
        return saved
    match = request.accept_languages.best_match(list(SUPPORTED_LANGUAGES))
    return match if match in SUPPORTED_LANGUAGES else "en"


def localized(key, lang=None):
    return TEXT.get(lang or current_language(), TEXT["en"]).get(key, key)


class ContactForm(FlaskForm):
    name = StringField()
    email = EmailField()
    subject = StringField()
    message = TextAreaField()
    website = StringField()  # Honeypot field.
    submit = SubmitField()

    def __init__(self, lang="en", *args, **kwargs):
        super().__init__(*args, **kwargs)
        ar = lang == "ar"
        self.name.validators = [DataRequired(message="اكتب اسمك من فضلك." if ar else "Please enter your name."), Length(max=80, message="الاسم طويل جدًا." if ar else "Name is too long.")]
        self.email.validators = [DataRequired(message="أدخل بريدك الإلكتروني." if ar else "Please enter your email."), Email(message="تحقّق من صيغة البريد." if ar else "Please check the email format."), Length(max=160)]
        self.subject.validators = [DataRequired(message="اكتب عنوانًا مختصرًا لطلبك." if ar else "Please add a short subject."), Length(max=120)]
        self.message.validators = [DataRequired(message="أضف تفاصيل بسيطة عن المشروع." if ar else "Please add some project details."), Length(min=15, max=4000, message="اكتب من 15 إلى 4000 حرف." if ar else "Please use 15 to 4000 characters.")]


class FeedbackForm(FlaskForm):
    name = StringField()
    rating = SelectField(choices=[("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5")])
    comment = TextAreaField()
    publish_consent = BooleanField()
    website = StringField()  # Honeypot field.
    submit = SubmitField()

    def __init__(self, lang="en", *args, **kwargs):
        super().__init__(*args, **kwargs)
        ar = lang == "ar"
        self.name.validators = [Optional(), Length(max=80, message="الاسم طويل جدًا." if ar else "Name is too long.")]
        self.rating.validators = [DataRequired(message="اختر تقييمًا." if ar else "Choose a rating."), AnyOf(["1", "2", "3", "4", "5"], message="اختر تقييمًا من 1 إلى 5." if ar else "Choose a rating from 1 to 5.")]
        self.comment.validators = [Optional(), Length(max=600, message="يجب ألا يتجاوز التعليق 600 حرف." if ar else "Comments must be 600 characters or fewer.")]


class AdminLoginForm(FlaskForm):
    password = PasswordField(validators=[DataRequired()])
    submit = SubmitField()


class AdminActionForm(FlaskForm):
    decision = HiddenField(validators=[DataRequired(), AnyOf(["approve", "reject"])])
    submit = SubmitField()


class LogoutForm(FlaskForm):
    submit = SubmitField()


def _connect_db():
    path = Path(DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=8)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def db_connection():
    connection = _connect_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with db_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                comment TEXT NOT NULL DEFAULT '',
                publish_consent INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
                created_at TEXT NOT NULL
            )
        """)


init_db()


def send_contact_email(form, lang):
    host = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    try:
        port = int(os.getenv("MAIL_PORT", "587"))
    except ValueError:
        return False
    username = os.getenv("MAIL_USERNAME", "").strip()
    password = os.getenv("MAIL_PASSWORD", "").strip()
    recipient = os.getenv("CONTACT_EMAIL", PROFILE["email"]).strip()
    if not username or not password or not recipient:
        return False
    msg = EmailMessage()
    safe_subject = " ".join(form.subject.data.replace("\r", " ").replace("\n", " ").split())
    msg["Subject"] = f"{'طلب من الموقع' if lang == 'ar' else 'Portfolio enquiry'}: {safe_subject}"
    msg["From"] = username
    msg["To"] = recipient
    msg["Reply-To"] = form.email.data.strip()
    msg.set_content(
        f"New portfolio enquiry / طلب جديد من الموقع\n\n"
        f"Name / الاسم: {form.name.data.strip()}\n"
        f"Email / البريد: {form.email.data.strip()}\n"
        f"Subject / الموضوع: {form.subject.data.strip()}\n\n"
        f"Message / التفاصيل:\n{form.message.data.strip()}\n"
    )
    with smtplib.SMTP(host, port, timeout=12) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
    return True


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
    if request.path.startswith("/manage-feedback"):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Cache-Control"] = "no-store"
    return response


def feedback_summary(lang):
    with db_connection() as connection:
        summary = connection.execute("SELECT COUNT(*) AS total, AVG(rating) AS average FROM feedback WHERE status = 'approved'").fetchone()
        published = connection.execute("SELECT id, name, rating, comment, created_at FROM feedback WHERE status='approved' AND publish_consent=1 AND TRIM(comment) <> '' ORDER BY id DESC LIMIT 6").fetchall()
    return {
        "total": int(summary["total"] or 0),
        "average": round(float(summary["average"] or 0), 1),
        "items": [dict(row) for row in published],
    }


@app.route("/", methods=["GET", "POST"])
def home():
    lang = current_language()
    t = TEXT[lang]
    contact_form = ContactForm(lang=lang)
    feedback_form = FeedbackForm(lang=lang)

    if request.method == "POST":
        if contact_form.website.data:
            flash(t["contact_spam"], "error")
            return redirect(url_for("home", _anchor="contact"))
        if contact_form.validate_on_submit():
            try:
                if send_contact_email(contact_form, lang):
                    flash(t["contact_success"], "success")
                else:
                    flash(t["contact_disabled"], "error")
            except (OSError, smtplib.SMTPException, ValueError):
                app.logger.exception("Contact email delivery failed")
                flash(t["contact_failed"], "error")
            return redirect(url_for("home", _anchor="contact"))
        flash(t["contact_invalid"], "error")

    role = PROFILE["role_ar"] if lang == "ar" else PROFILE["role_en"]
    location = PROFILE["location_ar"] if lang == "ar" else PROFILE["location_en"]
    about = PROFILE["about_ar"] if lang == "ar" else PROFILE["about_en"]
    feedback = feedback_summary(lang)
    return render_template(
        "index.html", lang=lang, t=t, profile=PROFILE, role=role, location=location,
        about=about, services=SERVICES, projects=PROJECTS,
        initial_project_count=INITIAL_PROJECT_COUNT, support_url=SUPPORT_URL,
        contact_form=contact_form, feedback_form=feedback_form, feedback=feedback,
        year=datetime.now().year, theme=request.cookies.get("site_theme", "dark"),
    )


@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    lang = current_language()
    t = TEXT[lang]
    form = FeedbackForm(lang=lang)
    if form.website.data:
        flash(t["review_spam"], "error")
        return redirect(url_for("home", _anchor="feedback"))
    if not form.validate_on_submit():
        flash(t["review_validation"], "error")
        return redirect(url_for("home", _anchor="feedback"))
    name = (form.name.data or "").strip()[:80]
    comment = (form.comment.data or "").strip()[:600]
    consent = bool(form.publish_consent.data)
    # The comment/name are kept private unless the visitor explicitly consents to publication.
    if not consent:
        name_for_storage = ""
        comment_for_storage = ""
    else:
        name_for_storage = name
        comment_for_storage = comment
    with db_connection() as connection:
        connection.execute(
            "INSERT INTO feedback (name, rating, comment, publish_consent, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (name_for_storage, int(form.rating.data), comment_for_storage, int(consent), datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
    flash(t["review_submitted"], "success")
    return redirect(url_for("home", _anchor="feedback"))


@app.route("/manage-feedback", methods=["GET", "POST"])
def manage_feedback():
    lang = current_language()
    t = TEXT[lang]
    login_form = AdminLoginForm()
    logout_form = LogoutForm()
    action_form = AdminActionForm()
    admin_password = os.getenv("FEEDBACK_ADMIN_PASSWORD", "")

    if request.method == "POST":
        if not admin_password:
            flash(t["admin_unconfigured"], "error")
            return redirect(url_for("manage_feedback"))
        if login_form.validate_on_submit():
            candidate = login_form.password.data or ""
            if hmac.compare_digest(candidate, admin_password):
                session["feedback_admin_authenticated"] = True
                flash(t["admin_title"], "success")
            else:
                flash(t["admin_bad_password"], "error")
        return redirect(url_for("manage_feedback"))

    pending = []
    if session.get("feedback_admin_authenticated"):
        with db_connection() as connection:
            pending = [dict(row) for row in connection.execute("SELECT id, name, rating, comment, publish_consent, created_at FROM feedback WHERE status='pending' ORDER BY id ASC").fetchall()]
    return render_template(
        "feedback_admin.html", lang=lang, t=t, login_form=login_form,
        action_form=action_form, logout_form=logout_form, authenticated=bool(session.get("feedback_admin_authenticated")),
        configured=bool(admin_password), pending=pending, theme=request.cookies.get("site_theme", "dark"),
    )


@app.route("/manage-feedback/<int:feedback_id>", methods=["POST"])
def moderate_feedback(feedback_id):
    if not session.get("feedback_admin_authenticated"):
        abort(403)
    form = AdminActionForm()
    if not form.validate_on_submit():
        abort(400)
    decision = "approved" if form.decision.data == "approve" else "rejected"
    with db_connection() as connection:
        cursor = connection.execute("UPDATE feedback SET status=? WHERE id=? AND status='pending'", (decision, feedback_id))
        if cursor.rowcount == 0:
            abort(404)
    flash(TEXT[current_language()]["review_saved"], "success")
    return redirect(url_for("manage_feedback"))


@app.route("/manage-feedback/logout", methods=["POST"])
def logout_feedback_admin():
    if not session.get("feedback_admin_authenticated"):
        abort(403)
    form = LogoutForm()
    if not form.validate_on_submit():
        abort(400)
    session.pop("feedback_admin_authenticated", None)
    return redirect(url_for("manage_feedback"))


@app.route("/language/<lang>")
def set_language(lang):
    if lang not in SUPPORTED_LANGUAGES:
        abort(404)
    response = redirect(url_for("home"))
    next_path = request.args.get("next", "")
    # Accept only local relative paths; never turn the language switch into an open redirect.
    parsed = urlparse(next_path)
    if next_path.startswith("/") and not next_path.startswith("//") and not parsed.netloc:
        response = redirect(next_path)
    response.set_cookie("site_lang", lang, max_age=60 * 60 * 24 * 365, httponly=True, secure=request.is_secure, samesite="Lax", path="/")
    return response


@app.route("/health")
def health():
    return {"status": "ok"}, 200


@app.route("/robots.txt")
def robots():
    base = os.getenv("SITE_URL", "").rstrip("/")
    sitemap_line = f"Sitemap: {base}/sitemap.xml\n" if base else ""
    from flask import Response
    return Response("User-agent: *\nAllow: /\nDisallow: /manage-feedback\n" + sitemap_line, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    from flask import Response
    base = escape(os.getenv("SITE_URL", "").rstrip("/"))
    if not base:
        return Response("SITE_URL is not configured", status=503, mimetype="text/plain")
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{base}/</loc></url></urlset>'
    return Response(xml, mimetype="application/xml")


@app.errorhandler(404)
def not_found(_error):
    lang = current_language()
    return render_template("404.html", lang=lang, t=TEXT[lang], profile=PROFILE, theme=request.cookies.get("site_theme", "dark")), 404


@app.errorhandler(413)
def too_large(_error):
    flash(TEXT[current_language()]["request_too_large"], "error")
    return redirect(url_for("home", _anchor="contact"))


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
