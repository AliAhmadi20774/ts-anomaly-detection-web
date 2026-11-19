from rest_framework import serializers


class DatPreviewSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField(allow_empty_file=True), min_length=1, max_length=100)
    file_format = serializers.ChoiceField(choices=("auto", "current", "legacy"), default="auto")

    def validate_files(self, files: list) -> list:
        if sum(uploaded_file.size for uploaded_file in files) > 128 * 1024 * 1024:
            raise serializers.ValidationError("The selected files exceed the 128 MiB batch limit.")
        return files
