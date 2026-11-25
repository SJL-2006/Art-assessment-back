"""为「高中音乐」课程补充试题数据（幂等，按 course+stem 去重）。"""
from django.core.management.base import BaseCommand

from apps.questionbank.models import Chapter, Course, Question
from apps.users.models import User

# (章节, 题型, 难度, 年级, 题干, 选项, 答案, 解析, 分值)
HIGH_SCHOOL_QUESTIONS = [
    # ---- 音乐鉴赏 ----
    ("音乐鉴赏", "single", "easy", "高一", "《黄河大合唱》的曲作者是？",
     [{"key": "A", "text": "冼星海"}, {"key": "B", "text": "聂耳"},
      {"key": "C", "text": "贺绿汀"}, {"key": "D", "text": "马可"}],
     "A", "《黄河大合唱》由冼星海作曲、光未然作词。", 2),
    ("音乐鉴赏", "single", "medium", "高一", "旋律清新婉转的《茉莉花》是哪个地区的民歌？",
     [{"key": "A", "text": "江苏"}, {"key": "B", "text": "新疆"},
      {"key": "C", "text": "内蒙古"}, {"key": "D", "text": "陕北"}],
     "A", "《茉莉花》是流传于江苏一带的民间小调。", 2),
    ("音乐鉴赏", "single", "medium", "高二", "《欢乐颂》出自贝多芬的哪部作品？",
     [{"key": "A", "text": "《第九交响曲》"}, {"key": "B", "text": "《第五交响曲》"},
      {"key": "C", "text": "《第六交响曲》"}, {"key": "D", "text": "《月光奏鸣曲》"}],
     "A", "《欢乐颂》是贝多芬《第九交响曲》第四乐章的主题。", 2),
    ("音乐鉴赏", "judge", "easy", "高一", "《义勇军进行曲》的曲作者是聂耳。",
     [], "正确", "《义勇军进行曲》由聂耳作曲、田汉作词。", 2),
    ("音乐鉴赏", "single", "hard", "高三", "下列属于西洋管弦乐队中铜管乐器的是？",
     [{"key": "A", "text": "长笛"}, {"key": "B", "text": "圆号"},
      {"key": "C", "text": "单簧管"}, {"key": "D", "text": "双簧管"}],
     "B", "圆号属于铜管乐器；长笛、单簧管、双簧管属于木管乐器。", 2),

    # ---- 歌唱 ----
    ("歌唱", "single", "medium", "高二", "「美声唱法」起源于哪个国家？",
     [{"key": "A", "text": "意大利"}, {"key": "B", "text": "德国"},
      {"key": "C", "text": "法国"}, {"key": "D", "text": "俄罗斯"}],
     "A", "美声唱法起源于意大利。", 2),
    ("歌唱", "judge", "medium", "高二", "「气沉丹田」是歌唱中常用的呼吸要领。",
     [], "正确", "歌唱多采用胸腹式呼吸，气息下沉（气沉丹田）。", 2),

    # ---- 演奏 ----
    ("演奏", "single", "easy", "高一", "古筝属于哪一类民族乐器？",
     [{"key": "A", "text": "弹拨乐器"}, {"key": "B", "text": "拉弦乐器"},
      {"key": "C", "text": "吹管乐器"}, {"key": "D", "text": "打击乐器"}],
     "A", "古筝属于弹拨乐器。", 2),
    ("演奏", "single", "medium", "高二", "京剧的主要伴奏乐器是？",
     [{"key": "A", "text": "二胡"}, {"key": "B", "text": "京胡"},
      {"key": "C", "text": "板胡"}, {"key": "D", "text": "琵琶"}],
     "B", "京胡是京剧的主要伴奏乐器。", 2),
    ("演奏", "judge", "easy", "高一", "古琴是我国最古老的弹拨乐器之一。",
     [], "正确", "古琴是我国最古老、最具代表性的弹拨乐器之一。", 2),
    ("演奏", "single", "hard", "高三", "下列乐器中属于打击乐器的是？",
     [{"key": "A", "text": "小提琴"}, {"key": "B", "text": "定音鼓"},
      {"key": "C", "text": "大提琴"}, {"key": "D", "text": "长笛"}],
     "B", "定音鼓属于打击乐器。", 2),

    # ---- 音乐编创 ----
    ("音乐编创", "single", "medium", "高二", "以 4/4 拍记谱，每小节共有几拍？",
     [{"key": "A", "text": "2拍"}, {"key": "B", "text": "3拍"},
      {"key": "C", "text": "4拍"}, {"key": "D", "text": "6拍"}],
     "C", "4/4 拍表示以四分音符为一拍，每小节四拍。", 2),
    ("音乐编创", "judge", "medium", "高三", "十二平均律最早由我国明代音乐家朱载堉计算出。",
     [], "正确", "朱载堉在明代计算出十二平均律，早于西方。", 2),
    ("音乐编创", "single", "medium", "高二", "下列选项中，属于音乐基本要素的是？",
     [{"key": "A", "text": "旋律"}, {"key": "B", "text": "色彩"},
      {"key": "C", "text": "构图"}, {"key": "D", "text": "透视"}],
     "A", "旋律是音乐的基本要素之一。", 2),
]


class Command(BaseCommand):
    help = "为「高中音乐」课程补充试题（幂等，按 course+stem 去重）。"

    def handle(self, *args, **options):
        course, _ = Course.objects.get_or_create(
            name="高中音乐", defaults={"code": "music"}
        )
        creator = User.objects.filter(username="admin").first()

        chapter_cache = {}
        created = 0
        skipped = 0
        for chapter_name, qtype, difficulty, grade, stem, opts, answer, analysis, score in HIGH_SCHOOL_QUESTIONS:
            chapter = chapter_cache.get(chapter_name)
            if chapter is None:
                chapter, _ = Chapter.objects.get_or_create(
                    course=course, name=chapter_name, parent=None,
                    defaults={"sort": len(chapter_cache)},
                )
                chapter_cache[chapter_name] = chapter

            if Question.objects.filter(course=course, stem=stem).exists():
                skipped += 1
                continue

            Question.objects.create(
                course=course,
                chapter=chapter,
                qtype=qtype,
                difficulty=difficulty,
                grade=grade,
                stem=stem,
                options=opts,
                answer=answer,
                analysis=analysis,
                score=score,
                status=Question.STATUS_APPROVED,
                creator=creator,
            )
            created += 1

        self.stdout.write(
            f"高中音乐 试题：新建 {created} 道，跳过 {skipped} 道；章节 {len(chapter_cache)} 个。"
        )
