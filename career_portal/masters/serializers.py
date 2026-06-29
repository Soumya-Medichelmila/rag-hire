from rest_framework import serializers

from .models import (
    Department,
    Skill,
    Location
)


class DepartmentSerializer(serializers.ModelSerializer):

    class Meta:

        model = Department

        fields = '__all__'


class SkillSerializer(serializers.ModelSerializer):

    class Meta:

        model = Skill

        fields = '__all__'


class LocationSerializer(serializers.ModelSerializer):

    class Meta:

        model = Location

        fields = '__all__'