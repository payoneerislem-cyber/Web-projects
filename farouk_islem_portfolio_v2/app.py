from flask import Flask, render_template

app = Flask(__name__)

# عدّل هذه البيانات قبل النشر، خصوصًا البريد وروابط حساباتك.
PROFILE = {
    "name": "Farouk Islem",
    "name_ar": "فاروق إسلام",
    "role": "مطوّر ويب ومهتم بالذكاء الاصطناعي",
    "location": "الجزائر",
    "email": "islemislem5560@gmail.com",
    "intro": "أساعد الأفراد وأصحاب الأعمال على تقديم أفكارهم للعالم الرقمي من خلال مواقع وتجارب ويب.",
    "about": "أطوّر مواقع وتجارب ويب تركّز على الوضوح وسهولة الاستخدام، من الصفحات التعريفية إلى تطبيقات الويب. كما أستكشف توظيف الذكاء الاصطناعي لبناء أدوات عملية تساعد على إنجاز العمل بصورة أفضل.",
    "github": "https://github.com/payoneerislem-cyber/Web-projects.git",
    "linkedin": "",
    "instagram": "https://www.instagram.com/faroukislemfarwq/",
    "whatsapp": "https://wa.me/+213779985001",
}

SKILLS = [
    ("تصميم وتطوير مواقع الويب", "مواقع سريعة ومتجاوبة مع مختلف الشاشات"),
    ("تطبيقات الويب", "بناء وظائف عملية وتجارب استخدام واضحة"),
    ("Python و Flask", "تطوير تطبيقات ويب حسب احتياج المشروع"),
    ("الذكاء الاصطناعي", "استكشاف دمج أدوات AI في سير العمل"),
]

# استبدل أمثلة المشاريع بمشاريعك الفعلية قبل النشر.
PROJECTS = [
    {
        "title": "Kora Live",
        "category": "تطبيق ويب",
        "description": "واجهة ويب لمتابعة كرة القدم، صُمّمت لعرض المعلومات بطريقة منظمة وسهلة التصفح.",
        "stack": ["Python", "Flask", "واجهة ويب"],
        "url": "",
        "status": "مشروع تجريبي",
    },
    {
        "title": "Lumina",
        "category": "مشروع ويب",
        "description": "مشروع لتطوير واجهة ويب حديثة مع اهتمام بتنظيم الملفات وسهولة الاستخدام.",
        "stack": ["HTML", "CSS", "JavaScript"],
        "url": "https://lumina-app-3zje.onrender.com/",
        "status": "مشروع تجريبي",
    },
    {
        "title": "مشروعك القادم",
        "category": "مساحة مفتوحة",
        "description": "هذا المكان جاهز لعرض مشروع آخر أو دراسة حالة أو أداة بنيتها لمساعدة المستخدمين.",
        "stack": ["مشروع جديد", "قيد الإضافة"],
        "url": "",
        "status": "قريبًا",
    },
]

@app.route("/")
def home():
    return render_template("index.html", profile=PROFILE, skills=SKILLS, projects=PROJECTS, profile_image='profile.png')

if __name__ == "__main__":
    app.run(debug=True)
