from django.db import models
from utils.models import BaseModel

from .answer import Answer


class AnswerSheet(BaseModel):
    """
    the answer sheet of the QUESTIONNAIRE which MEMBER answers in

    FIELDS
    member: the MEMBER who answers the QUESTIONNAIRE and the ANSWER_SHEET is belonged
    questioner: the QUESTIONNAIRE which the ANSWER_SHEET is belonged
    """
    member = models.ForeignKey("account_management.Member", on_delete=models.CASCADE)
    questioner = models.ForeignKey("hamyar.Questioner", on_delete=models.CASCADE)

    def __str__(self):
        return str(self.questioner)

    @property
    def is_fully_answered(self):
        answer = Answer.objects.filter(answer_sheet=self).last()
        if answer:
            question_choice = answer.question_choice
            if not question_choice.has_next:
                return True

        return False
