from rest_framework import serializers

from apps.content.models import FunClassKnowledge


class FunClassKnowledgeSerializer(serializers.ModelSerializer):
    """趣味课堂知识序列化。"""

    subject_display = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = FunClassKnowledge
        fields = [
            "id",
            "title",
            "subject",
            "subject_display",
            "content",
            "image",
            "image_url",
            "sort",
            "is_published",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_subject_display(self, obj):
        return obj.get_subject_display()

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            try:
                return request.build_absolute_uri(obj.image.url)
            except ValueError:
                return ""
        return ""
