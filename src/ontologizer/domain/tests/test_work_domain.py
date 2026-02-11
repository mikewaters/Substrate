# """Unit tests for work domain models."""

# from datetime import datetime

# import pytest

# from ontology.domain.work import (
#     Activity,
#     Effort,
#     Experiment,
#     Research,
#     Study,
#     Task,
#     Thinking,
# )


# class TestActivity:
#     """Test the base Activity domain model."""

#     def test_activity_creation_with_required_fields(self):
#         """Test creating an Activity with only required fields."""
#         activity = Activity(title="Test Activity", activity_type="Task")

#         assert activity.title == "Test Activity"
#         assert activity.activity_type == "Task"
#         assert activity.identifier.startswith("act:")
#         assert activity.description is None
#         assert activity.url is None
#         assert activity.created_by is None

#     def test_activity_creation_with_all_fields(self):
#         """Test creating an Activity with all fields."""
#         now = datetime.now()
#         activity_id = "act:test"

#         activity = Activity(
#             title="Complete Activity",
#             activity_type="Effort",
#             identifier="act:complete-activity",
#             id=activity_id,
#             description="A complete activity with all fields",
#             url="https://example.com",
#             created_by="user@example.com",
#             created_on=now,
#             last_updated_on=now,
#         )

#         assert activity.title == "Complete Activity"
#         assert activity.activity_type == "Effort"
#         assert activity.identifier == "act:complete-activity"
#         assert activity.id == activity_id
#         assert activity.description == "A complete activity with all fields"
#         assert activity.url == "https://example.com"
#         assert activity.created_by == "user@example.com"
#         assert activity.created_on == now
#         assert activity.last_updated_on == now

#     def test_activity_identifier_auto_generation(self):
#         """Test that identifier is auto-generated from title."""
#         activity = Activity(title="My Test Activity", activity_type="Task")

#         assert activity.identifier == "act:my-test-activity"

#     def test_activity_custom_identifier(self):
#         """Test that custom identifier is preserved."""
#         activity = Activity(
#             title="Test",
#             activity_type="Task",
#             identifier="custom:identifier",
#         )

#         assert activity.identifier == "custom:identifier"

#     def test_activity_str_representation(self):
#         """Test string representation of Activity."""
#         activity = Activity(title="Test Activity", activity_type="Task")

#         assert str(activity) == "Task(Test Activity)"


# class TestEffort:
#     """Test the Effort domain model."""

#     def test_effort_creation(self):
#         """Test creating an Effort."""
#         effort = Effort(title="Build New Feature")

#         assert effort.title == "Build New Feature"
#         assert effort.activity_type == "Effort"
#         assert isinstance(effort, Activity)

#     def test_effort_str_representation(self):
#         """Test string representation of Effort."""
#         effort = Effort(title="My Project")

#         assert str(effort) == "Effort(My Project)"


# class TestExperiment:
#     """Test the Experiment domain model."""

#     def test_experiment_creation(self):
#         """Test creating an Experiment."""
#         experiment = Experiment(title="Try New Approach")

#         assert experiment.title == "Try New Approach"
#         assert experiment.activity_type == "Experiment"
#         assert isinstance(experiment, Activity)

#     def test_experiment_str_representation(self):
#         """Test string representation of Experiment."""
#         experiment = Experiment(title="Testing Something")

#         assert str(experiment) == "Experiment(Testing Something)"


# class TestResearch:
#     """Test the Research domain model."""

#     def test_research_creation(self):
#         """Test creating a Research activity."""
#         research = Research(title="Investigate Solution")

#         assert research.title == "Investigate Solution"
#         assert research.activity_type == "Research"
#         assert isinstance(research, Activity)

#     def test_research_str_representation(self):
#         """Test string representation of Research."""
#         research = Research(title="Study the Problem")

#         assert str(research) == "Research(Study the Problem)"


# class TestStudy:
#     """Test the Study domain model."""

#     def test_study_creation(self):
#         """Test creating a Study activity."""
#         study = Study(title="Learn Python")

#         assert study.title == "Learn Python"
#         assert study.activity_type == "Study"
#         assert isinstance(study, Activity)

#     def test_study_str_representation(self):
#         """Test string representation of Study."""
#         study = Study(title="Master SQLAlchemy")

#         assert str(study) == "Study(Master SQLAlchemy)"


# class TestTask:
#     """Test the Task domain model."""

#     def test_task_creation(self):
#         """Test creating a Task."""
#         task = Task(title="Write Documentation")

#         assert task.title == "Write Documentation"
#         assert task.activity_type == "Task"
#         assert isinstance(task, Activity)

#     def test_task_str_representation(self):
#         """Test string representation of Task."""
#         task = Task(title="Fix Bug #123")

#         assert str(task) == "Task(Fix Bug #123)"


# class TestThinking:
#     """Test the Thinking domain model."""

#     def test_thinking_creation(self):
#         """Test creating a Thinking activity."""
#         thinking = Thinking(title="Reflect on Architecture")

#         assert thinking.title == "Reflect on Architecture"
#         assert thinking.activity_type == "Thinking"
#         assert isinstance(thinking, Activity)

#     def test_thinking_str_representation(self):
#         """Test string representation of Thinking."""
#         thinking = Thinking(title="Contemplate Design")

#         assert str(thinking) == "Thinking(Contemplate Design)"


# class TestActivityTypeInheritance:
#     """Test that all activity types properly inherit from Activity."""

#     @pytest.mark.parametrize(
#         "activity_class,expected_type",
#         [
#             (Effort, "Effort"),
#             (Experiment, "Experiment"),
#             (Research, "Research"),
#             (Study, "Study"),
#             (Task, "Task"),
#             (Thinking, "Thinking"),
#         ],
#     )
#     def test_activity_inheritance(self, activity_class, expected_type):
#         """Test that each activity class inherits from Activity and has correct type."""
#         instance = activity_class(title="Test")

#         assert isinstance(instance, Activity)
#         assert instance.activity_type == expected_type
