"""演示数据初始化：账号 + 课程/章节/已审核试题，便于在 Apifox 联调。"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.questionbank.models import Chapter, Course, Question
from apps.users.models import User


class Command(BaseCommand):
    help = "初始化演示数据：超级用户/教师账号 + 音乐/美术课程、章节与已审核试题。"

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) 账号：admin 为超级用户（is_superuser 绕过所有角色校验），teacher 为教师
        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={"role": User.ROLE_QB_ADMIN, "real_name": "题库管理员"},
        )
        admin.is_staff = True
        admin.is_superuser = True
        admin.role = User.ROLE_QB_ADMIN
        admin.set_password("admin123456")
        admin.save()

        teacher, _ = User.objects.get_or_create(
            username="teacher",
            defaults={"role": User.ROLE_TEACHER, "real_name": "张老师"},
        )
        teacher.role = User.ROLE_TEACHER
        teacher.set_password("teacher123456")
        teacher.save()

        # 2) 课程（音乐 / 美术）
        music, _ = Course.objects.get_or_create(code="music", defaults={"name": "音乐"})
        art, _ = Course.objects.get_or_create(code="art", defaults={"name": "美术"})

        # 3) 章节
        music_ch1, _ = Chapter.objects.get_or_create(course=music, name="乐理基础", defaults={"sort": 1})
        music_ch2, _ = Chapter.objects.get_or_create(course=music, name="视唱练耳", defaults={"sort": 2})
        art_ch1, _ = Chapter.objects.get_or_create(course=art, name="色彩基础", defaults={"sort": 1})

        # 4) 已审核试题：课程、章节、题型、难度、题干、选项、答案、解析、分值
        questions = [
            (music, music_ch1, "single", "easy", "五线谱共有几条线？",
             [{"key": "A", "text": "三条"}, {"key": "B", "text": "四条"}, {"key": "C", "text": "五条"}, {"key": "D", "text": "六条"}],
             "C", "五线谱由五条平行线组成。", 2),
            (music, music_ch1, "single", "medium", "下列哪个是全音符？",
             [{"key": "A", "text": "♩"}, {"key": "B", "text": "♪"}, {"key": "C", "text": "𝅝"}, {"key": "D", "text": "𝅗𝅥"}],
             "C", "全音符是空心椭圆且不带符杆。", 2),
            (music, music_ch1, "multiple", "medium", "以下哪些属于西洋管弦乐器的木管组？",
             [{"key": "A", "text": "长笛"}, {"key": "B", "text": "双簧管"}, {"key": "C", "text": "小提琴"}, {"key": "D", "text": "单簧管"}],
             "ABD", "长笛、双簧管、单簧管属木管组，小提琴属弦乐组。", 3),
            (music, music_ch1, "judge", "easy", "升记号 # 表示将音升高半音。",
             [], "正确", "# 为升记号，表示升高半音。", 1),
            (music, music_ch2, "fill", "medium", "国际标准音 A4 的频率为 ____ Hz。",
             [], "440", "国际标准音 A4 = 440Hz。", 2),
            (music, music_ch2, "listening", "easy", "听辨：该段旋律的主音唱名是？",
             [], "do", "听力题示例，实际需配合音频资源。", 2),
            (music, music_ch2, "sight", "medium", "视唱：请按给定谱例视唱并上传音频。",
             [], "（见谱例）", "视唱题示例，实际需配合谱例资源。", 5),
            (art, art_ch1, "single", "easy", "美术中的三原色是指？",
             [{"key": "A", "text": "红黄蓝"}, {"key": "B", "text": "红绿蓝"}, {"key": "C", "text": "青品黄"}, {"key": "D", "text": "黑白灰"}],
             "A", "美术三原色为红、黄、蓝。", 2),
            (art, art_ch1, "single", "medium", "暖色调通常给人什么样的感觉？",
             [{"key": "A", "text": "寒冷"}, {"key": "B", "text": "温暖"}, {"key": "C", "text": "平静"}, {"key": "D", "text": "忧郁"}],
             "B", "暖色调（红橙黄）给人温暖、热烈的感觉。", 2),
            (art, art_ch1, "multiple", "medium", "以下哪些颜色属于冷色？",
             [{"key": "A", "text": "蓝"}, {"key": "B", "text": "绿"}, {"key": "C", "text": "红"}, {"key": "D", "text": "紫"}],
             "AB", "蓝、绿为冷色，红为暖色。", 3),
            (art, art_ch1, "judge", "easy", "素描中，暗部与亮部之间的过渡层次叫灰面。",
             [], "正确", "素描三大面：亮面、灰面、暗面。", 1),
            (art, art_ch1, "fill", "easy", "色彩三要素是色相、明度和 ____。",
             [], "纯度", "色彩三要素：色相、明度、纯度。", 2),
        ]

        created = 0
        for course, chapter, qtype, difficulty, stem, opts, answer, analysis, score in questions:
            _, is_new = Question.objects.get_or_create(
                course=course, chapter=chapter, qtype=qtype, stem=stem,
                defaults={
                    "difficulty": difficulty,
                    "options": opts,
                    "answer": answer,
                    "analysis": analysis,
                    "score": score,
                    "grade": "一年级",
                    "status": Question.STATUS_APPROVED,
                    "creator": admin,
                    "reviewer": admin,
                },
            )
            created += int(is_new)

        self.stdout.write(self.style.SUCCESS("演示数据初始化完成。"))
        self.stdout.write(f"  账号：admin / admin123456（超级用户，role=qb_admin，可访问全部接口）")
        self.stdout.write(f"  账号：teacher / teacher123456（教师，可访问题库/组卷，无审核权限）")
        self.stdout.write(f"  课程：音乐、美术；新增试题 {created} 道（均为已审核状态）。")
