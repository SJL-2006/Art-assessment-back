"""补全题库空档：初中音乐、初中美术、高中美术（幂等，按 course+stem 去重）。

现有题库覆盖：
- generate_questions：小学 1–6 年级（音乐/美术）
- create_high_school_questions：高中音乐（高一~高三）

缺口：
- 初中（七年级~九年级）音乐、美术
- 高中美术（高一~高三）

本命令补上以上三个空档，每题 status=approved，随机组卷可直接抽到。
运行：python manage.py create_supplementary_questions
"""
from django.core.management.base import BaseCommand

from apps.questionbank.models import Chapter, Course, Question
from apps.users.models import User

# 题目元组格式：(章节, 题型, 难度, 年级, 题干, 选项, 答案, 解析, 分值)
# 题型：single 单选 / judge 判断 / fill 填空；判断与填空题的选项传空列表 []。

# ------------------------- 初中音乐（七年级~九年级） -------------------------
JUNIOR_MUSIC_QUESTIONS = [
    # ---- 乐理基础 ----
    ("乐理基础", "single", "easy", "七年级", "简谱中唱名 sol 对应的数字是？",
     [{"key": "A", "text": "1"}, {"key": "B", "text": "2"},
      {"key": "C", "text": "5"}, {"key": "D", "text": "6"}],
     "C", "简谱用 1、2、3、4、5、6、7 表示 do、re、mi、fa、sol、la、si，sol 对应 5。", 2),
    ("乐理基础", "single", "easy", "七年级", "五线谱由几条平行线组成？",
     [{"key": "A", "text": "三条"}, {"key": "B", "text": "四条"},
      {"key": "C", "text": "五条"}, {"key": "D", "text": "六条"}],
     "C", "五线谱由五条平行线组成。", 2),
    ("乐理基础", "single", "easy", "七年级", "以 4/4 拍记谱，全音符唱几拍？",
     [{"key": "A", "text": "1拍"}, {"key": "B", "text": "2拍"},
      {"key": "C", "text": "3拍"}, {"key": "D", "text": "4拍"}],
     "D", "全音符在 4/4 拍中唱四拍。", 2),
    ("乐理基础", "single", "easy", "七年级", "2/4 拍的强弱规律是？",
     [{"key": "A", "text": "强、弱"}, {"key": "B", "text": "强、弱、弱"},
      {"key": "C", "text": "弱、强"}, {"key": "D", "text": "强、弱、次强、弱"}],
     "A", "2/4 拍为“强、弱”。", 2),
    ("乐理基础", "single", "medium", "八年级", "附点音符的时值在原音符基础上增加多少？",
     [{"key": "A", "text": "四分之一"}, {"key": "B", "text": "三分之一"},
      {"key": "C", "text": "一半"}, {"key": "D", "text": "一倍"}],
     "C", "附点增加原音符时值的一半。", 2),
    ("乐理基础", "single", "medium", "八年级", "自然大调音阶中，哪两个相邻音之间是半音关系？",
     [{"key": "A", "text": "mi—fa、si—do"}, {"key": "B", "text": "do—re、re—mi"},
      {"key": "C", "text": "fa—sol、la—si"}, {"key": "D", "text": "sol—la、la—si"}],
     "A", "自然大调音阶中 mi—fa、si—do 为半音关系。", 2),
    ("乐理基础", "single", "hard", "九年级", "6/8 拍表示每小节有几个八分音符？",
     [{"key": "A", "text": "3个"}, {"key": "B", "text": "4个"},
      {"key": "C", "text": "6个"}, {"key": "D", "text": "8个"}],
     "C", "6/8 拍表示每小节有六个八分音符。", 2),
    ("乐理基础", "judge", "easy", "七年级", "全音符的时值比四分音符长。",
     [], "正确", "全音符等于四个四分音符的时值。", 1),
    ("乐理基础", "fill", "medium", "九年级", "我国传统五声音阶由宫、商、角、徵、____五个音组成。",
     [], "羽", "五声音阶为宫、商、角、徵、羽。", 2),

    # ---- 歌唱与欣赏 ----
    ("歌唱与欣赏", "single", "easy", "七年级", "《义勇军进行曲》的曲作者是？",
     [{"key": "A", "text": "冼星海"}, {"key": "B", "text": "聂耳"},
      {"key": "C", "text": "贺绿汀"}, {"key": "D", "text": "刘炽"}],
     "B", "《义勇军进行曲》由聂耳作曲、田汉作词。", 2),
    ("歌唱与欣赏", "single", "medium", "八年级", "《黄河大合唱》的曲作者是？",
     [{"key": "A", "text": "聂耳"}, {"key": "B", "text": "冼星海"},
      {"key": "C", "text": "马可"}, {"key": "D", "text": "贺绿汀"}],
     "B", "《黄河大合唱》由冼星海作曲、光未然作词。", 2),
    ("歌唱与欣赏", "single", "easy", "七年级", "人声按音域由高到低，男声分为？",
     [{"key": "A", "text": "男高音、男中音、男低音"}, {"key": "B", "text": "男高音、男低音"},
      {"key": "C", "text": "只有男高音"}, {"key": "D", "text": "男高音、男中音"}],
     "A", "男声按音域分为男高音、男中音、男低音。", 2),
    ("歌唱与欣赏", "single", "medium", "九年级", "音乐术语“渐强”的意大利语标记是？",
     [{"key": "A", "text": "crescendo"}, {"key": "B", "text": "dim."},
      {"key": "C", "text": "rit."}, {"key": "D", "text": "a tempo"}],
     "A", "渐强记作 crescendo（缩写 cresc.）。", 2),
    ("歌唱与欣赏", "single", "medium", "八年级", "混声四部合唱由哪四个声部组成？",
     [{"key": "A", "text": "女高、女低、男高、男低"}, {"key": "B", "text": "女高、女中、男高、男低"},
      {"key": "C", "text": "女高、女低、男高、男中"}, {"key": "D", "text": "女高、女中、男中、男低"}],
     "A", "混声四部合唱由女高音、女低音、男高音、男低音组成。", 2),
    ("歌唱与欣赏", "judge", "easy", "七年级", "《义勇军进行曲》由聂耳作曲、田汉作词。",
     [], "正确", "《义勇军进行曲》由聂耳作曲、田汉作词。", 1),

    # ---- 乐器与民族音乐 ----
    ("乐器与民族音乐", "single", "easy", "七年级", "二胡属于哪一类乐器？",
     [{"key": "A", "text": "弹拨乐器"}, {"key": "B", "text": "拉弦乐器"},
      {"key": "C", "text": "吹管乐器"}, {"key": "D", "text": "打击乐器"}],
     "B", "二胡用弓拉奏，属拉弦乐器。", 2),
    ("乐器与民族音乐", "single", "easy", "七年级", "琵琶属于哪一类乐器？",
     [{"key": "A", "text": "拉弦乐器"}, {"key": "B", "text": "弹拨乐器"},
      {"key": "C", "text": "吹管乐器"}, {"key": "D", "text": "打击乐器"}],
     "B", "琵琶用手指弹拨琴弦，属弹拨乐器。", 2),
    ("乐器与民族音乐", "single", "easy", "八年级", "唢呐属于哪一类乐器？",
     [{"key": "A", "text": "拉弦乐器"}, {"key": "B", "text": "弹拨乐器"},
      {"key": "C", "text": "吹管乐器"}, {"key": "D", "text": "打击乐器"}],
     "C", "唢呐靠吹气振动发声，属吹管乐器。", 2),
    ("乐器与民族音乐", "single", "medium", "八年级", "京剧的主要伴奏乐器是？",
     [{"key": "A", "text": "二胡"}, {"key": "B", "text": "京胡"},
      {"key": "C", "text": "板胡"}, {"key": "D", "text": "琵琶"}],
     "B", "京胡是京剧的主要伴奏乐器。", 2),
    ("乐器与民族音乐", "single", "medium", "九年级", "民歌《茉莉花》主要流传于哪个地区？",
     [{"key": "A", "text": "东北"}, {"key": "B", "text": "江苏"},
      {"key": "C", "text": "西藏"}, {"key": "D", "text": "新疆"}],
     "B", "《茉莉花》是流传于江苏一带的民间小调。", 2),
    ("乐器与民族音乐", "single", "medium", "九年级", "马头琴是哪个民族的代表性拉弦乐器？",
     [{"key": "A", "text": "维吾尔族"}, {"key": "B", "text": "蒙古族"},
      {"key": "C", "text": "藏族"}, {"key": "D", "text": "傣族"}],
     "B", "马头琴是蒙古族的代表性拉弦乐器。", 2),
    ("乐器与民族音乐", "judge", "easy", "八年级", "古筝属于弹拨乐器。",
     [], "正确", "古筝用手指弹拨琴弦，属弹拨乐器。", 1),
]

# ------------------------- 初中美术（七年级~九年级） -------------------------
JUNIOR_ART_QUESTIONS = [
    # ---- 色彩基础 ----
    ("色彩基础", "single", "easy", "七年级", "美术中的三原色是？",
     [{"key": "A", "text": "红、黄、蓝"}, {"key": "B", "text": "红、绿、蓝"},
      {"key": "C", "text": "青、品、黄"}, {"key": "D", "text": "黑、白、灰"}],
     "A", "美术（颜料）三原色为红、黄、蓝。", 2),
    ("色彩基础", "single", "medium", "九年级", "色光的三原色是？",
     [{"key": "A", "text": "红、黄、蓝"}, {"key": "B", "text": "红、绿、蓝"},
      {"key": "C", "text": "青、品、黄"}, {"key": "D", "text": "黑、白、灰"}],
     "B", "色光三原色为红、绿、蓝。", 2),
    ("色彩基础", "single", "easy", "七年级", "三原色两两相配可以得到？",
     [{"key": "A", "text": "三间色"}, {"key": "B", "text": "复色"},
      {"key": "C", "text": "同类色"}, {"key": "D", "text": "对比色"}],
     "A", "三原色两两相配得三间色（橙、绿、紫）。", 2),
    ("色彩基础", "single", "easy", "八年级", "色彩的三要素是？",
     [{"key": "A", "text": "色相、明度、纯度"}, {"key": "B", "text": "色相、冷暖、明度"},
      {"key": "C", "text": "红、黄、蓝"}, {"key": "D", "text": "明暗、冷暖、色相"}],
     "A", "色彩三要素为色相、明度、纯度。", 2),
    ("色彩基础", "single", "easy", "七年级", "下列哪个颜色属于暖色？",
     [{"key": "A", "text": "蓝"}, {"key": "B", "text": "绿"},
      {"key": "C", "text": "红"}, {"key": "D", "text": "紫"}],
     "C", "红、橙、黄为暖色。", 2),
    ("色彩基础", "judge", "easy", "七年级", "黄色与蓝色混合可以得到绿色。",
     [], "正确", "黄＋蓝＝绿。", 1),

    # ---- 素描与造型 ----
    ("素描与造型", "single", "easy", "七年级", "素描中的三大面是指？",
     [{"key": "A", "text": "亮面、灰面、暗面"}, {"key": "B", "text": "正面、侧面、背面"},
      {"key": "C", "text": "红面、黄面、蓝面"}, {"key": "D", "text": "上面、下面、前面"}],
     "A", "素描三大面为亮面、灰面、暗面。", 2),
    ("素描与造型", "single", "medium", "八年级", "素描五大调子中明暗对比最强烈的是？",
     [{"key": "A", "text": "高光"}, {"key": "B", "text": "灰面"},
      {"key": "C", "text": "明暗交界线"}, {"key": "D", "text": "反光"}],
     "C", "明暗交界线处明暗对比最强烈。", 2),
    ("素描与造型", "single", "easy", "八年级", "只有一个消失点的透视叫？",
     [{"key": "A", "text": "平行透视"}, {"key": "B", "text": "成角透视"},
      {"key": "C", "text": "散点透视"}, {"key": "D", "text": "俯视"}],
     "A", "平行透视（一点透视）只有一个消失点。", 2),
    ("素描与造型", "single", "medium", "九年级", "有两个消失点的透视叫？",
     [{"key": "A", "text": "平行透视"}, {"key": "B", "text": "成角透视"},
      {"key": "C", "text": "散点透视"}, {"key": "D", "text": "仰视"}],
     "B", "成角透视（两点透视）有两个消失点。", 2),

    # ---- 中国画与美术史 ----
    ("中国画与美术史", "single", "easy", "七年级", "中国画按题材分为三大类，不包括下列哪项？",
     [{"key": "A", "text": "人物画"}, {"key": "B", "text": "山水画"},
      {"key": "C", "text": "花鸟画"}, {"key": "D", "text": "风景画"}],
     "D", "中国画三大类为人物、山水、花鸟。", 2),
    ("中国画与美术史", "single", "easy", "七年级", "中国画的“文房四宝”是？",
     [{"key": "A", "text": "笔、墨、纸、砚"}, {"key": "B", "text": "琴、棋、书、画"},
      {"key": "C", "text": "纸、笔、墨、刀"}, {"key": "D", "text": "笔、墨、砚、画"}],
     "A", "文房四宝为笔、墨、纸、砚。", 2),
    ("中国画与美术史", "single", "easy", "八年级", "《清明上河图》的作者是？",
     [{"key": "A", "text": "张择端"}, {"key": "B", "text": "顾恺之"},
      {"key": "C", "text": "吴道子"}, {"key": "D", "text": "黄公望"}],
     "A", "《清明上河图》是北宋张择端所作。", 2),
    ("中国画与美术史", "single", "easy", "八年级", "《蒙娜丽莎》的作者是？",
     [{"key": "A", "text": "达·芬奇"}, {"key": "B", "text": "米开朗基罗"},
      {"key": "C", "text": "拉斐尔"}, {"key": "D", "text": "梵高"}],
     "A", "《蒙娜丽莎》是达·芬奇的名作。", 2),
    ("中国画与美术史", "single", "easy", "九年级", "中国画中“岁寒三友”是指？",
     [{"key": "A", "text": "松、竹、梅"}, {"key": "B", "text": "梅、兰、竹"},
      {"key": "C", "text": "松、柏、梅"}, {"key": "D", "text": "竹、菊、梅"}],
     "A", "岁寒三友为松、竹、梅。", 2),
    ("中国画与美术史", "single", "medium", "九年级", "被称为“画圣”的画家是？",
     [{"key": "A", "text": "吴道子"}, {"key": "B", "text": "顾恺之"},
      {"key": "C", "text": "王维"}, {"key": "D", "text": "阎立本"}],
     "A", "唐代吴道子被称为“画圣”。", 2),
    ("中国画与美术史", "judge", "easy", "八年级", "《清明上河图》描绘的是北宋都城汴京。",
     [], "正确", "《清明上河图》描绘北宋都城汴京（今开封）。", 1),
]

# ------------------------- 高中美术（高一~高三） -------------------------
HIGH_ART_QUESTIONS = [
    # ---- 美术鉴赏 ----
    ("美术鉴赏", "single", "easy", "高一", "“文艺复兴三杰”不包括下列哪位？",
     [{"key": "A", "text": "达·芬奇"}, {"key": "B", "text": "米开朗基罗"},
      {"key": "C", "text": "拉斐尔"}, {"key": "D", "text": "梵高"}],
     "D", "文艺复兴三杰为达·芬奇、米开朗基罗、拉斐尔。", 2),
    ("美术鉴赏", "single", "medium", "高二", "印象派因莫奈的哪幅作品而得名？",
     [{"key": "A", "text": "《日出·印象》"}, {"key": "B", "text": "《星月夜》"},
      {"key": "C", "text": "《草地上的午餐》"}, {"key": "D", "text": "《睡莲》"}],
     "A", "莫奈《日出·印象》使印象派得名。", 2),
    ("美术鉴赏", "single", "medium", "高二", "下列属于后印象派代表画家的是？",
     [{"key": "A", "text": "莫奈"}, {"key": "B", "text": "梵高"},
      {"key": "C", "text": "雷诺阿"}, {"key": "D", "text": "德加"}],
     "B", "梵高、塞尚、高更为后印象派代表。", 2),
    ("美术鉴赏", "single", "medium", "高三", "油画《格尔尼卡》的作者是？",
     [{"key": "A", "text": "毕加索"}, {"key": "B", "text": "达利"},
      {"key": "C", "text": "马蒂斯"}, {"key": "D", "text": "蒙克"}],
     "A", "《格尔尼卡》是毕加索的反战名作。", 2),
    ("美术鉴赏", "single", "hard", "高三", "中国画“六法”由谁提出？",
     [{"key": "A", "text": "谢赫"}, {"key": "B", "text": "顾恺之"},
      {"key": "C", "text": "张彦远"}, {"key": "D", "text": "王维"}],
     "A", "南齐谢赫在《古画品录》中提出“六法”。", 2),

    # ---- 绘画 ----
    ("绘画", "single", "easy", "高一", "中国画按表现手法主要分为哪两大类？",
     [{"key": "A", "text": "工笔与写意"}, {"key": "B", "text": "油画与版画"},
      {"key": "C", "text": "素描与速写"}, {"key": "D", "text": "水彩与水粉"}],
     "A", "中国画按表现手法主要分工笔和写意两大类。", 2),
    ("绘画", "single", "medium", "高二", "中国画用墨讲究“墨分五色”，五色指？",
     [{"key": "A", "text": "焦、浓、重、淡、清"}, {"key": "B", "text": "红、黄、蓝、白、黑"},
      {"key": "C", "text": "干、湿、浓、淡、清"}, {"key": "D", "text": "深、浅、明、暗、灰"}],
     "A", "墨分五色为焦、浓、重、淡、清。", 2),
    ("绘画", "single", "medium", "高二", "油画常用的稀释剂是？",
     [{"key": "A", "text": "松节油"}, {"key": "B", "text": "水"},
      {"key": "C", "text": "胶水"}, {"key": "D", "text": "酒精"}],
     "A", "油画颜料用松节油等油类稀释。", 2),
    ("绘画", "single", "easy", "高一", "以画马著称的近现代画家是？",
     [{"key": "A", "text": "齐白石"}, {"key": "B", "text": "徐悲鸿"},
      {"key": "C", "text": "张大千"}, {"key": "D", "text": "潘天寿"}],
     "B", "徐悲鸿以画马闻名。", 2),
    ("绘画", "judge", "easy", "高一", "工笔和写意是按表现手法区分的中国画两大种类。",
     [], "正确", "工笔精勾细染，写意重神韵，是按表现手法区分的两大类。", 1),

    # ---- 雕塑与建筑 ----
    ("雕塑与建筑", "single", "easy", "高一", "雕塑一般分为圆雕和？",
     [{"key": "A", "text": "浮雕"}, {"key": "B", "text": "壁画"},
      {"key": "C", "text": "版画"}, {"key": "D", "text": "油画"}],
     "A", "雕塑一般分为圆雕与浮雕。", 2),
    ("雕塑与建筑", "single", "medium", "高二", "雕像《大卫》的作者是？",
     [{"key": "A", "text": "达·芬奇"}, {"key": "B", "text": "米开朗基罗"},
      {"key": "C", "text": "拉斐尔"}, {"key": "D", "text": "罗丹"}],
     "B", "《大卫》是米开朗基罗的雕塑。", 2),
    ("雕塑与建筑", "single", "medium", "高一", "秦始皇陵兵马俑的材质主要是？",
     [{"key": "A", "text": "陶"}, {"key": "B", "text": "青铜"},
      {"key": "C", "text": "石"}, {"key": "D", "text": "木"}],
     "A", "兵马俑为陶制。", 2),
    ("雕塑与建筑", "single", "medium", "高三", "敦煌莫高窟的壁画主要属于？",
     [{"key": "A", "text": "佛教艺术"}, {"key": "B", "text": "道教艺术"},
      {"key": "C", "text": "宫廷艺术"}, {"key": "D", "text": "民间艺术"}],
     "A", "莫高窟壁画以佛教题材为主。", 2),
    ("雕塑与建筑", "judge", "medium", "高二", "《创世纪》是米开朗基罗为西斯廷教堂绘制的天顶画。",
     [], "正确", "西斯廷教堂天顶画为米开朗基罗所绘《创世纪》。", 1),
]

# 课程块：(课程名, 课程代码, 题目列表)
COURSE_BLOCKS = [
    ("初中音乐", "music_junior", JUNIOR_MUSIC_QUESTIONS),
    ("初中美术", "art_junior", JUNIOR_ART_QUESTIONS),
    ("高中美术", "art_senior", HIGH_ART_QUESTIONS),
]


class Command(BaseCommand):
    help = "补全题库空档：初中音乐、初中美术、高中美术（幂等，按 course+stem 去重）。"

    def handle(self, *args, **options):
        creator = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(role=User.ROLE_QB_ADMIN).first()
        )

        total_created = 0
        total_skipped = 0
        for course_name, course_code, questions in COURSE_BLOCKS:
            course, _ = Course.objects.get_or_create(
                name=course_name, defaults={"code": course_code},
            )
            chapter_cache = {}
            created = skipped = 0
            for chapter_name, qtype, difficulty, grade, stem, opts, answer, analysis, score in questions:
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

            total_created += created
            total_skipped += skipped
            self.stdout.write(
                f"{course_name}：新建 {created} 道，跳过 {skipped} 道；章节 {len(chapter_cache)} 个。"
            )

        self.stdout.write(
            self.style.SUCCESS(f"补全完成：共新建 {total_created} 道，跳过 {total_skipped} 道。")
        )
