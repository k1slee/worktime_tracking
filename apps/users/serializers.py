from rest_framework import serializers
from .models import User, Department, Employee

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'parent']
        read_only_fields = ['id']

class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    full_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'employee_id', 'email', 'first_name', 'last_name',
            'department', 'department_name', 'role', 'position', 'phone',
            'is_active', 'date_joined', 'full_name'
        ]
        read_only_fields = ['date_joined']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class EmployeeSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    master_name = serializers.CharField(source='master.get_full_name', read_only=True)
    
    class Meta:
        model = Employee
        fields = [
            'id', 'user', 'user_details', 'master', 'master_name',
            'hire_date', 'is_active'
        ]