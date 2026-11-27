"""初始化演示数据（幂等）：账号 + 组织 + 班级 + 题库（音乐/美术，覆盖选择题与判断题/难度/年级）+ 已发布试卷。

运行：python manage.py seed_demo
"""
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.classroom.models import APPROVED, ClassRoom, ClassStudent
from apps.exam.models import Paper, PaperPublish, PaperQuestion
from apps.org.models import Region, School
from apps.questionbank.models import Chapter, Course, Question
from apps.users.models import User


class Command(BaseCommand):
    help = "初始化演示数据：账号/组织/班级 + 音乐/美术题库（选择题与判断题）+ 已发布试卷。"

    @transaction.atomic
    def handle(self, *args, **options):
        # ── 1) 行政区 → 学校 → 班级 ──
        province, _ = Region.objects.get_or_create(
            code="510000", defaults={"name": "四川省", "level": Region.LEVEL_PROVINCE},
        )
        city, _ = Region.objects.get_or_create(
            code="510100", defaults={"name": "成都市", "level": Region.LEVEL_CITY, "parent": province},
        )
        district, _ = Region.objects.get_or_create(
            code="510104", defaults={"name": "锦江区", "level": Region.LEVEL_DISTRICT, "parent": city},
        )
        school, _ = School.objects.get_or_create(
            code="SCH001", defaults={"name": "测试小学", "region": district},
        )
        klass3, _ = ClassRoom.objects.get_or_create(
            code="CLS003", defaults={"name": "三年级一班", "grade": "三年级", "school": school},
        )
        klass5, _ = ClassRoom.objects.get_or_create(
            code="CLS005", defaults={"name": "五年级二班", "grade": "五年级", "school": school},
        )

        # ── 2) 各角色账号（幂等，重复运行会重置角色与密码）──
        def make_user(username, role, real_name, password, **extra):
            user, _ = User.objects.get_or_create(username=username, defaults={"role": role})
            user.role = role
            user.real_name = real_name
            for key, value in extra.items():
                setattr(user, key, value)
            user.is_active = True
            user.set_password(password)
            user.save()
            return user

        admin = make_user("admin", User.ROLE_QB_ADMIN, "题库管理员", "admin123456")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

        teacher = make_user(
            "teacher", User.ROLE_TEACHER, "李老师", "teacher123456",
            school=school, region=district,
        )
        student3 = make_user(
            "student", User.ROLE_STUDENT, "小明", "student123456",
            school=school, region=district, student_no="S2024001",
        )
        student5 = make_user(
            "student5", User.ROLE_STUDENT, "小红", "student123456",
            school=school, region=district, student_no="S2024005",
        )
        make_user("school", User.ROLE_SCHOOL, "校管理员", "school123456", school=school, region=district)
        make_user("district", User.ROLE_DISTRICT, "区县管理员", "district123456", region=district)
        make_user("city", User.ROLE_CITY, "市州管理员", "city123456", region=city)
        make_user("province", User.ROLE_PROVINCE, "省级管理员", "province123456", region=province)

        # ── 3) 学生加入班级（已通过审核）──
        ClassStudent.objects.get_or_create(klass=klass3, student=student3, defaults={"status": APPROVED})
        ClassStudent.objects.get_or_create(klass=klass5, student=student5, defaults={"status": APPROVED})


        # 4) 课程 + 章节 + 已审核试题（音乐 19 + 美术 17，共 36 道，覆盖选择题/判断题/难度/年级）
        music, _ = Course.objects.get_or_create(name="音乐", defaults={"code": "music"})
        art, _ = Course.objects.get_or_create(name="美术", defaults={"code": "art"})

        music_ch1, _ = Chapter.objects.get_or_create(course=music, name="乐理基础", defaults={"sort": 1})
        art_ch1, _ = Chapter.objects.get_or_create(course=art, name="色彩基础", defaults={"sort": 1})
        art_ch2, _ = Chapter.objects.get_or_create(course=art, name="造型基础", defaults={"sort": 2})

        # (课程, 章节, 题型, 难度, 年级, 题干, 选项, 答案, 解析, 分值)
        question_specs = [
            # ========== 音乐（19 道） ==========
            # 三年级（含演示试卷沿用的原 4 道）
            (music, music_ch1, "single", "easy", "三年级", "以下哪个是高音谱号？",
             [{"key": "A", "text": "𝄞"}, {"key": "B", "text": "𝄢"}, {"key": "C", "text": "𝄡"}, {"key": "D", "text": "𝄣"}],
             "A", "高音谱号（G 谱号）形似 𝄞。", 2),
            (music, music_ch1, "single", "easy", "三年级", "四分音符的时值相当于几个八分音符？",
             [{"key": "A", "text": "1个"}, {"key": "B", "text": "2个"}, {"key": "C", "text": "3个"}, {"key": "D", "text": "4个"}],
             "B", "四分音符的时值等于 2 个八分音符。", 2),
            (music, music_ch1, "multiple", "easy", "三年级", "下列哪些属于西洋乐器？",
             [{"key": "A", "text": "小提琴"}, {"key": "B", "text": "二胡"}, {"key": "C", "text": "钢琴"}, {"key": "D", "text": "长笛"}],
             "ACD", "二胡是中国民族乐器，其余为西洋乐器。", 3),
            (music, music_ch1, "judge", "easy", "三年级", "标准音 a1 的频率是 440Hz。",
             [], "正确", "国际标准音 a1 = 440Hz。", 1),
            # 一年级
            (music, music_ch1, "single", "easy", "一年级", "唱歌时应该用怎样的声音？",
             [{"key": "A", "text": "大声喊叫"}, {"key": "B", "text": "自然好听的声音"}, {"key": "C", "text": "小声嘟囔"}, {"key": "D", "text": "闭着嘴哼"}],
             "B", "歌唱要使用自然、好听的声音，不喊唱。", 2),
            (music, music_ch1, "judge", "easy", "一年级", "《两只老虎》是一首儿童歌曲。",
             [], "正确", "《两只老虎》是广为流传的儿童歌曲。", 1),
            (music, music_ch1, "single", "easy", "一年级", "听到进行曲时，人们通常会联想到？",
             [{"key": "A", "text": "睡觉"}, {"key": "B", "text": "踏步前进"}, {"key": "C", "text": "安静看书"}, {"key": "D", "text": "哭泣"}],
             "B", "进行曲节奏鲜明，适合踏步前进。", 2),
            # 二年级
            (music, music_ch1, "single", "easy", "二年级", "二拍子的强弱规律是？",
             [{"key": "A", "text": "强弱弱"}, {"key": "B", "text": "强弱"}, {"key": "C", "text": "强强弱"}, {"key": "D", "text": "弱强"}],
             "B", "二拍子为强弱交替。", 2),
            (music, music_ch1, "judge", "easy", "二年级", "力度记号 f 表示强，p 表示弱。",
             [], "正确", "f = forte 强，p = piano 弱。", 1),
            (music, music_ch1, "multiple", "medium", "二年级", "以下哪些是打击乐器？",
             [{"key": "A", "text": "小鼓"}, {"key": "B", "text": "三角铁"}, {"key": "C", "text": "小提琴"}, {"key": "D", "text": "碰铃"}],
             "ABD", "小提琴属于弦乐器。", 3),
            # 四年级
            (music, music_ch1, "single", "medium", "四年级", "三拍子的强弱规律是？",
             [{"key": "A", "text": "强弱弱"}, {"key": "B", "text": "强弱"}, {"key": "C", "text": "强强弱弱"}, {"key": "D", "text": "弱强弱"}],
             "A", "三拍子为强弱弱。", 2),
            (music, music_ch1, "multiple", "medium", "四年级", "以下哪些属于中国民族乐器？",
             [{"key": "A", "text": "二胡"}, {"key": "B", "text": "琵琶"}, {"key": "C", "text": "长笛"}, {"key": "D", "text": "古筝"}],
             "ABD", "长笛是西洋木管乐器。", 3),
            (music, music_ch1, "judge", "medium", "四年级", "附点音符会把前面音符的时值延长一半。",
             [], "正确", "附点延长原音符时值的一半。", 1),
            # 五年级
            (music, music_ch1, "single", "medium", "五年级", "下列哪个力度记号表示“很强”？",
             [{"key": "A", "text": "p"}, {"key": "B", "text": "mp"}, {"key": "C", "text": "ff"}, {"key": "D", "text": "mf"}],
             "C", "ff = fortissimo，表示很强。", 2),
            (music, music_ch1, "multiple", "medium", "五年级", "以下哪些属于西洋管弦乐队的弦乐组？",
             [{"key": "A", "text": "小提琴"}, {"key": "B", "text": "中提琴"}, {"key": "C", "text": "大提琴"}, {"key": "D", "text": "长号"}],
             "ABC", "长号属于铜管组。", 3),
            (music, music_ch1, "judge", "medium", "五年级", "升记号 # 表示将音升高半音。",
             [], "正确", "# 为升记号，表示升高半音。", 1),
            # 六年级
            (music, music_ch1, "single", "medium", "六年级", "大调音阶中，第几级音是主音？",
             [{"key": "A", "text": "第一级"}, {"key": "B", "text": "第三级"}, {"key": "C", "text": "第五级"}, {"key": "D", "text": "第七级"}],
             "A", "主音是音阶的第一级音。", 2),
            (music, music_ch1, "multiple", "hard", "六年级", "以下哪些属于常见的曲式结构？",
             [{"key": "A", "text": "一部曲式"}, {"key": "B", "text": "二部曲式"}, {"key": "C", "text": "三部曲式"}, {"key": "D", "text": "回旋曲式"}],
             "ABCD", "以上均属常见曲式结构。", 3),
            (music, music_ch1, "judge", "hard", "六年级", "休止符表示声音停止，同时也占一定时值。",
             [], "正确", "休止符表示静默，但仍占相应时值。", 1),
            # ========== 美术（17 道） ==========
            # 一年级
            (art, art_ch1, "single", "easy", "一年级", "美术中的三原色是指哪三种颜色？",
             [{"key": "A", "text": "红黄蓝"}, {"key": "B", "text": "红绿蓝"}, {"key": "C", "text": "青品黄"}, {"key": "D", "text": "黑白灰"}],
             "A", "美术三原色为红、黄、蓝。", 2),
            (art, art_ch1, "judge", "easy", "一年级", "红色和黄色混合可以调出橙色。",
             [], "正确", "红 + 黄 = 橙。", 1),
            (art, art_ch1, "single", "easy", "一年级", "以下哪种工具适合辅助画直线？",
             [{"key": "A", "text": "直尺"}, {"key": "B", "text": "橡皮"}, {"key": "C", "text": "调色盘"}, {"key": "D", "text": "毛笔"}],
             "A", "直尺可以辅助画出笔直的线条。", 2),
            # 二年级
            (art, art_ch1, "single", "easy", "二年级", "暖色调通常给人什么样的感觉？",
             [{"key": "A", "text": "寒冷"}, {"key": "B", "text": "温暖"}, {"key": "C", "text": "平静"}, {"key": "D", "text": "忧郁"}],
             "B", "暖色调（红橙黄）给人温暖、热烈的感觉。", 2),
            (art, art_ch1, "judge", "easy", "二年级", "对称的图形左右两边大小一样。",
             [], "正确", "对称图形两边完全重合。", 1),
            # 三年级
            (art, art_ch1, "multiple", "medium", "三年级", "以下哪些颜色属于冷色？",
             [{"key": "A", "text": "蓝"}, {"key": "B", "text": "绿"}, {"key": "C", "text": "红"}, {"key": "D", "text": "橙"}],
             "AB", "蓝、绿为冷色，红、橙为暖色。", 3),
            (art, art_ch1, "judge", "easy", "三年级", "素描中，暗部与亮部之间的过渡层次叫灰面。",
             [], "正确", "素描三大面：亮面、灰面、暗面。", 1),
            (art, art_ch2, "single", "medium", "三年级", "下列哪种线条最能表现平静、稳定的感觉？",
             [{"key": "A", "text": "水平直线"}, {"key": "B", "text": "波浪线"}, {"key": "C", "text": "折线"}, {"key": "D", "text": "放射线"}],
             "A", "水平直线给人平静、稳定的感觉。", 2),
            # 四年级
            (art, art_ch2, "single", "medium", "四年级", "透视中，远处的物体看起来会怎样？",
             [{"key": "A", "text": "更大"}, {"key": "B", "text": "更小"}, {"key": "C", "text": "不变"}, {"key": "D", "text": "完全消失"}],
             "B", "近大远小是透视的基本规律。", 2),
            (art, art_ch2, "multiple", "medium", "四年级", "以下哪些属于绘画的基本造型元素？",
             [{"key": "A", "text": "点"}, {"key": "B", "text": "线"}, {"key": "C", "text": "面"}, {"key": "D", "text": "体"}],
             "ABCD", "点、线、面、体是基本造型元素。", 3),
            (art, art_ch2, "judge", "medium", "四年级", "水彩画中，颜料越湿越容易相互晕染。",
             [], "正确", "湿画法下颜色容易相互晕染。", 1),
            # 五年级
            (art, art_ch2, "single", "medium", "五年级", "下列哪种构图方式最能强调主体居中的稳定感？",
             [{"key": "A", "text": "对称构图"}, {"key": "B", "text": "三角形构图"}, {"key": "C", "text": "对角线构图"}, {"key": "D", "text": "散点构图"}],
             "A", "对称构图稳定、庄重。", 2),
            (art, art_ch2, "multiple", "hard", "五年级", "以下哪些属于中国传统绘画的形式？",
             [{"key": "A", "text": "工笔"}, {"key": "B", "text": "写意"}, {"key": "C", "text": "油画"}, {"key": "D", "text": "水墨"}],
             "ABD", "油画属于西方绘画。", 3),
            (art, art_ch1, "judge", "medium", "五年级", "明度是指色彩的明暗程度。",
             [], "正确", "明度即色彩的明暗程度。", 1),
            # 六年级
            (art, art_ch2, "single", "hard", "六年级", "下列哪一项最能体现画面的空间层次？",
             [{"key": "A", "text": "重复同一颜色"}, {"key": "B", "text": "近实远虚"}, {"key": "C", "text": "所有物体画成同样大小"}, {"key": "D", "text": "只画轮廓"}],
             "B", "近实远虚能增强画面的空间感。", 2),
            (art, art_ch2, "multiple", "hard", "六年级", "以下哪些属于版画的形式？",
             [{"key": "A", "text": "木刻版画"}, {"key": "B", "text": "纸版画"}, {"key": "C", "text": "水彩画"}, {"key": "D", "text": "铜版画"}],
             "ABD", "水彩画不属于版画。", 3),
            (art, art_ch2, "judge", "hard", "六年级", "冷色调一般能给人安静、深远的感觉。",
             [], "正确", "冷色常带来安静、深远之感。", 1),
        ]

        created = 0
        for course, chapter, qtype, difficulty, grade, stem, opts, answer, analysis, score in question_specs:
            _, is_new = Question.objects.get_or_create(
                course=course,
                stem=stem,
                defaults={
                    "chapter": chapter,
                    "qtype": qtype,
                    "difficulty": difficulty,
                    "grade": grade,
                    "options": opts,
                    "answer": answer,
                    "analysis": analysis,
                    "score": score,
                    "status": Question.STATUS_APPROVED,
                    "creator": admin,
                    "reviewer": admin,
                },
            )
            created += int(is_new)

        # 5) 试卷 + 题目关联 + 发布（scope=class 命中「三年级一班」）
        paper_stems = [
            "以下哪个是高音谱号？",
            "四分音符的时值相当于几个八分音符？",
            "下列哪些属于西洋乐器？",
            "标准音 a1 的频率是 440Hz。",
        ]
        paper, _ = Paper.objects.get_or_create(
            title="三年级音乐正式测评",
            defaults={
                "ptype": Paper.TYPE_FORMAL,
                "subject": Paper.SUBJECT_MUSIC,
                "level": Paper.LEVEL_CLASS,
                "grade": "三年级",
                "duration": 30,
                "total_score": Decimal("20"),
                "status": Paper.STATUS_PUBLISHED,
                "creator": admin,
            },
        )
        paper_qs = Question.objects.filter(
            course=music, status=Question.STATUS_APPROVED, stem__in=paper_stems,
        ).order_by("id")
        for index, question in enumerate(paper_qs):
            PaperQuestion.objects.get_or_create(
                paper=paper, question=question, defaults={"sort": index + 1, "score": Decimal("5")},
            )

        publish, _ = PaperPublish.objects.get_or_create(
            paper=paper,
            scope_type=PaperPublish.SCOPE_CLASS,
            defaults={"target_class": klass3, "target_school": school, "status": PaperPublish.STATUS_PUBLISHED},
        )
        publish.target_class = klass3
        publish.target_school = school
        publish.status = PaperPublish.STATUS_PUBLISHED
        publish.save()

        # ── 7) 输出 ──
        total = Question.objects.filter(status=Question.STATUS_APPROVED).count()
        self.stdout.write(self.style.SUCCESS("演示数据初始化完成。"))
        self.stdout.write(f"  题库：已审核共 {total} 道（新增 {created}）")
        self.stdout.write(f"    音乐：{Question.objects.filter(course=music, status=Question.STATUS_APPROVED).count()} 道")
        self.stdout.write(f"    美术：{Question.objects.filter(course=art, status=Question.STATUS_APPROVED).count()} 道")
        self.stdout.write("  账号（角色 · 密码）：")
        self.stdout.write("    admin    / admin123456    （超级用户 · 题库管理员，可访问全部接口）")
        self.stdout.write("    teacher  / teacher123456  （教师，可评分/查看学生/导出）")
        self.stdout.write("    student  / student123456  （学生·三年级一班）")
        self.stdout.write("    student5 / student123456  （学生·五年级二班）")
        self.stdout.write("    school   / school123456   （学校管理员，可统计）")
        self.stdout.write("    district / district123456 （区县管理员，可统计）")
        self.stdout.write("    city     / city123456     （市州管理员，可统计）")
        self.stdout.write("    province / province123456 （省级管理员，可统计+参与率导出）")
        self.stdout.write("  数据链：四川省 → 成都市 → 锦江区 → 测试小学 → 三年级一班 / 五年级二班")
        self.stdout.write("  已发布试卷：三年级音乐正式测评（formal，总分 20，scope=class，4 道客观题）")        