"""创建教师提交的「待审核」试题，用于测试题库审核流程。

用法：
    python manage.py create_pending_questions

以用户名 teacher 的教师账号为创建人，向题库写入若干 status=pending 的题，
使「题库管理员-试题审核」页的待审核列表有内容可审。按 (课程, 题干) 幂等，重复执行不重复创建。
"""
from django.core.management.base import BaseCommand

from apps.questionbank.models import Course, Question
from apps.users.models import User

# 每题：course=课程名，qtype/difficulty/grade/options/answer/analysis/score 与前端提交格式一致
PENDING_QUESTIONS = [
    {
        "course": "初中音乐",
        "qtype": "single",
        "difficulty": "medium",
        "grade": "七年级",
        "stem": "在简谱中，唱名“sol”对应的数字是？",
        "options": [
            {"key": "A", "text": "1"},
            {"key": "B", "text": "2"},
            {"key": "C", "text": "5"},
            {"key": "D", "text": "6"},
        ],
        "answer": "C",
        "analysis": "简谱用 1、2、3、4、5、6、7 表示 do、re、mi、fa、sol、la、si，sol 对应 5。",
        "score": 2,
    },
    {
        "course": "初中音乐",
        "qtype": "judge",
        "difficulty": "easy",
        "grade": "八年级",
        "stem": "全音符的时值等于两个二分音符的时值之和。",
        "options": [],
        "answer": "对",
        "analysis": "全音符为四拍，二分音符为两拍，两个二分音符之和为四拍，故正确。",
        "score": 2,
    },
    {
        "course": "音乐鉴赏",
        "qtype": "single",
        "difficulty": "easy",
        "grade": "三年级",
        "stem": "下列乐器中，属于中国民族弹拨乐器的是？",
        "options": [
            {"key": "A", "text": "小提琴"},
            {"key": "B", "text": "琵琶"},
            {"key": "C", "text": "长笛"},
            {"key": "D", "text": "大提琴"},
        ],
        "answer": "B",
        "analysis": "琵琶是中国传统弹拨乐器；小提琴、大提琴是西洋弦乐器，长笛是西洋木管乐器。",
        "score": 2,
    },
    {
        "course": "美术",
        "qtype": "single",
        "difficulty": "medium",
        "grade": "七年级",
        "stem": "中国画按表现技法分类，主要分为哪两大类？",
        "options": [
            {"key": "A", "text": "工笔与写意"},
            {"key": "B", "text": "油画与版画"},
            {"key": "C", "text": "素描与速写"},
            {"key": "D", "text": "水彩与水粉"},
        ],
        "answer": "A",
        "analysis": "中国画按技法主要分工笔和写意两大类。",
        "score": 2,
    },
    {
        "course": "美术",
        "qtype": "judge",
        "difficulty": "easy",
        "grade": "六年级",
        "stem": "素描中常说的“三大面”是指亮面、灰面、暗面。",
        "options": [],
        "answer": "对",
        "analysis": "三大面即亮面、灰面、暗面，用于表现物体的立体感。",
        "score": 2,
    },
]


class Command(BaseCommand):
    help = "创建教师提交的待审核试题（status=pending），用于测试审核流程。"

    def handle(self, *args, **options):
        teacher = User.objects.filter(username="teacher", role=User.ROLE_TEACHER).first()
        if teacher is None:
            teacher = User.objects.create_user(
                username="teacher", password="123456",
                role=User.ROLE_TEACHER, real_name="测试教师",
            )
            self.stdout.write(self.style.WARNING("未找到 teacher 教师账号，已自动创建（密码 123456）。"))

        created = 0
        skipped = 0
        for item in PENDING_QUESTIONS:
            course = Course.objects.filter(name=item["course"], is_deleted=False).first()
            if course is None:
                self.stderr.write(f"课程不存在：{item['course']}")
                continue
            _, flag = Question.objects.get_or_create(
                course=course,
                stem=item["stem"],
                defaults={
                    "qtype": item["qtype"],
                    "difficulty": item["difficulty"],
                    "grade": item["grade"],
                    "options": item["options"],
                    "answer": item["answer"],
                    "analysis": item["analysis"],
                    "score": item["score"],
                    "status": Question.STATUS_PENDING,
                    "creator": teacher,
                },
            )
            if flag:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f"待审核试题：新建 {created} 道，已存在跳过 {skipped} 道（创建人：teacher）。")
        )
