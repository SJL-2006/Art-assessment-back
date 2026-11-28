"""seed_fun_contents：把学习材料名称改高级（占位/口语标题替换为 10 篇正式中文艺术材料）。

用法示例：
    python manage.py seed_fun_contents --dry-run
    python manage.py seed_fun_contents

只写 FunContent 数据（update_or_create 幂等 + 占位记录软删除），不改模型、不需要迁移、不改前端样式；
subject 只用 music / art / general，category 用正式分类，emoji 用真实表情，status=published，全省学生可见。
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.exam.models import FunContent
from apps.users.models import User

ARTICLES = [
    {
        "title": "音乐与情绪：旋律如何塑造心理感受",
        "subject": "music",
        "category": "音乐欣赏",
        "summary": "从旋律、节奏与和声入手，理解音乐如何影响情绪体验与记忆。",
        "content": (
            "音乐通过旋律的起伏、节奏的快慢和和声的松紧，影响人的呼吸、心跳与情绪体验。"
            "舒缓的旋律常让人放松，明亮的节奏更容易带来愉悦感。"
            "熟悉的音乐还会唤起与往事相关的场景和感受，因此音乐常被用于情绪调节和记忆回顾。"
        ),
        "fun_fact": "听到喜欢的音乐时，大脑的奖赏系统会被激活，产生愉悦感。",
        "emoji": "🎵",
        "color": "#5b8def",
        "read_minutes": 3,
    },
    {
        "title": "艺术的价值：从审美经验到人格养成",
        "subject": "general",
        "category": "艺术素养",
        "summary": "艺术学习不只是技能训练，也影响观察、表达与审美判断。",
        "content": (
            "艺术教育通过绘画、歌唱、欣赏和创作等活动，帮助学生练习观察、想象和表达。"
            "它不要求每个学生都成为艺术家，而是让人学会用多种方式理解世界、表达感受，"
            "并在合作与展示中建立自信。"
        ),
        "fun_fact": "艺术活动中同时调动视觉、听觉和动作等多个感官，有助于提升综合感知能力。",
        "emoji": "🌈",
        "color": "#8fb09a",
        "read_minutes": 3,
    },
    {
        "title": "敦煌壁画中的东方色彩体系",
        "subject": "art",
        "category": "美术鉴赏",
        "summary": "石青、石绿、土红等矿物颜料，构成了敦煌壁画独特的色彩语言。",
        "content": (
            "敦煌壁画历经千年，色彩依然鲜明，这与矿物颜料的使用密切相关。"
            "石青、石绿、土红、赭石等颜色来自天然矿物，稳定性强。"
            "画师通过色彩的对比与层次，表现人物、衣饰和宗教场景，也形成了具有东方特征的色彩语言。"
        ),
        "fun_fact": "部分矿物颜料价格高昂，古代画师会把它用在壁画最重要的人物和部位上。",
        "emoji": "🖼️",
        "color": "#c97d8b",
        "read_minutes": 4,
    },
    {
        "title": "交响乐队的声部构成与音色层次",
        "subject": "music",
        "category": "音乐欣赏",
        "summary": "弦乐、木管、铜管与打击乐四个声部，共同构成交响乐队。",
        "content": (
            "交响乐队通常由弦乐、木管、铜管和打击乐四个声部组成。"
            "弦乐组人数最多，音色统一；木管组善于表现不同的色彩；铜管组音量宏大；"
            "打击乐负责节奏和气氛。作曲家在总谱中安排各声部的进入与配合，形成丰富的音响层次。"
        ),
        "fun_fact": "交响乐队演出前，通常由双簧管吹出标准音 A，供全体乐手校音。",
        "emoji": "🎻",
        "color": "#7e9cc0",
        "read_minutes": 3,
    },
    {
        "title": "中国民族乐器的分类与音色特征",
        "subject": "music",
        "category": "民族音乐",
        "summary": "吹、拉、弹、打四类民族乐器，构成中国音乐独特的音色。",
        "content": (
            "中国民族乐器常按演奏方式分为吹、拉、弹、打四类。"
            "笛子、笙、唢呐属于吹管乐器；二胡、板胡属于拉弦乐器；"
            "琵琶、古筝、阮属于弹拨乐器；锣、鼓、钹属于打击乐器。"
            "不同材质和发声方式，让它们在合奏中形成鲜明的音色对比。"
        ),
        "fun_fact": "同一件民族乐器，演奏技法不同，音色也会明显变化，例如琵琶的弹、挑、轮指。",
        "emoji": "🪕",
        "color": "#d9a441",
        "read_minutes": 4,
    },
    {
        "title": "《清明上河图》中的宋代市井生活",
        "subject": "art",
        "category": "美术鉴赏",
        "summary": "通过人物、建筑与市集，观察北宋城市的日常生活。",
        "content": (
            "《清明上河图》以长卷形式描绘北宋汴京的城市生活。"
            "画中有桥梁、船只、店铺、车马和大量人物，细节丰富。"
            "观看时可以从人物动作、建筑结构和市集布局入手，理解当时的社会生活，"
            "也能体会画家对空间和节奏的安排。"
        ),
        "fun_fact": "画卷中人物数量众多，服饰、动作和职业各不相同，常被当作研究宋代生活的图像资料。",
        "emoji": "🏯",
        "color": "#b08968",
        "read_minutes": 5,
    },
    {
        "title": "京剧脸谱的色彩象征与舞台语言",
        "subject": "art",
        "category": "传统文化",
        "summary": "红、黑、白、蓝等脸谱颜色，在京剧中有相对固定的象征意义。",
        "content": (
            "京剧脸谱用色彩和纹样提示人物的性格与身份。"
            "红色常表示忠勇，黑色多表现刚直，白色常带贬义，蓝色和绿色多用于性格强烈或粗犷的角色。"
            "脸谱并不是简单的化妆，而是与唱腔、动作和剧情配合的舞台语言。"
        ),
        "fun_fact": "不同剧种的脸谱画法并不完全相同，同一颜色在不同剧种中的含义也可能有差异。",
        "emoji": "🎭",
        "color": "#c0392b",
        "read_minutes": 3,
    },
    {
        "title": "中国山水画的观看方式与留白",
        "subject": "art",
        "category": "美术鉴赏",
        "summary": "从构图、笔墨和留白入手，理解山水画中的观看方式。",
        "content": (
            "欣赏中国山水画，可以先看整体构图，再看山石、树木和水流的笔墨处理。"
            "画家常通过留白表现云雾、水面和空间，让观者在画面中移动视线。"
            "山水画不只是描绘风景，也寄托了画家对自然和人生的理解。"
        ),
        "fun_fact": "中国画中的“留白”不是没有画完，而是画面构图和意境的重要组成部分。",
        "emoji": "🏞️",
        "color": "#6b8e7b",
        "read_minutes": 4,
    },
    {
        "title": "节拍与节奏：音乐时间组织的两个维度",
        "subject": "music",
        "category": "乐理常识",
        "summary": "节拍提供稳定的时间框架，节奏则是具体声音的长短组合。",
        "content": (
            "节拍像音乐的骨架，提供稳定、循环的时间单位；节奏则是音符在实际进行中的长短组合。"
            "相同的节拍下，可以出现不同的节奏型，音乐的表情也会随之变化。"
            "学习时可以先拍出稳定节拍，再练习具体的节奏型。"
        ),
        "fun_fact": "节拍器可以帮助建立稳定的速度感，但音乐演奏中的速度仍会有细微的弹性变化。",
        "emoji": "🥁",
        "color": "#e07a5f",
        "read_minutes": 2,
    },
    {
        "title": "透视法：绘画空间的表现逻辑",
        "subject": "art",
        "category": "造型基础",
        "summary": "近大远小、消失点和视平线，是绘画中表现空间的基本方法。",
        "content": (
            "透视法通过近大远小、近实远虚和消失点等规律，让平面画面产生空间感。"
            "画建筑或街道时，先确定视平线和消失点，再安排物体的位置与大小，画面会更稳定。"
            "透视不是死板公式，而是帮助观察和表达的工具。"
        ),
        "fun_fact": "文艺复兴时期的画家系统研究透视法，使绘画中的空间表现更加准确。",
        "emoji": "📐",
        "color": "#5c7cfa",
        "read_minutes": 3,
    },
]

SLUG_EMOJIS = ["music-note", "mix-star", "art-palette", "art-brush"]
NEW_TITLES = [a["title"] for a in ARTICLES]


def _placeholder_qs():
    """返回需要软删除的旧占位记录（纯数字标题 / 英文 slug 封面，且非本次标题）。"""
    return FunContent.objects.filter(
        Q(title__regex=r"^\d+$")
        | Q(emoji__in=SLUG_EMOJIS)
    ).exclude(title__in=NEW_TITLES)


class Command(BaseCommand):
    help = "把学习材料名称改高级：替换为 10 篇正式中文艺术材料并软删除占位记录。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只统计将新增/更新/清理的数量，不写库")

    def _resolve_creator(self):
        """发布人：省级管理员优先，其次题库管理员。"""
        return (
            User.objects.filter(role=User.ROLE_PROVINCE, is_active=True).first()
            or User.objects.filter(role=User.ROLE_QB_ADMIN, is_active=True).first()
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        creator = self._resolve_creator()

        to_create = []
        to_update = []
        for item in ARTICLES:
            if FunContent.objects.filter(title=item["title"]).exists():
                to_update.append(item)
            else:
                to_create.append(item)

        placeholder_qs = _placeholder_qs()
        placeholders = placeholder_qs.count()

        self.stdout.write(self.style.SUCCESS("学习材料更新：" + ("（--dry-run，未写库）" if dry_run else "")))
        self.stdout.write(f"  新增：{len(to_create)} 篇")
        self.stdout.write(f"  更新：{len(to_update)} 篇")
        self.stdout.write(f"  清理旧占位：{placeholders} 篇")

        if dry_run:
            published = FunContent.objects.filter(status=FunContent.STATUS_PUBLISHED, is_deleted=False).count()
            if creator is None:
                self.stdout.write(self.style.WARNING("  未找到省级/题库管理员，creator 将为空"))
            self.stdout.write(f"  当前已发布：{published} 篇（执行后 {published + len(to_create)} 篇）")
            if placeholders:
                self.stdout.write("  将软删除的占位记录：")
                for f in placeholder_qs.order_by("id"):
                    self.stdout.write(f"    #{f.id} {f.title!r} emoji={f.emoji!r}")
            return

        # 清理旧占位（软删除，不硬删、不按 category 批量删，避免误伤老师自建内容）
        if placeholders:
            placeholder_qs.update(is_deleted=True, deleted_at=timezone.now())
            self.stdout.write(self.style.WARNING(f"已软删除旧占位记录 {placeholders} 篇"))

        # 写入 10 篇（update_or_create 幂等）
        if creator is None:
            self.stdout.write(self.style.WARNING("未找到省级/题库管理员，creator 将为空"))
        for item in ARTICLES:
            FunContent.objects.update_or_create(
                title=item["title"],
                defaults={
                    "subject": item["subject"],
                    "category": item["category"],
                    "summary": item["summary"],
                    "content": item["content"],
                    "fun_fact": item["fun_fact"],
                    "emoji": item["emoji"],
                    "color": item["color"],
                    "read_minutes": item["read_minutes"],
                    "status": FunContent.STATUS_PUBLISHED,
                    "creator": creator,
                    "school": None,
                    "target_class": None,
                    "published_at": timezone.now(),
                    "is_deleted": False,
                    "deleted_at": None,
                },
            )

        published = FunContent.objects.filter(status=FunContent.STATUS_PUBLISHED, is_deleted=False).count()
        self.stdout.write(f"  当前已发布：{published} 篇")
