from django import forms
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from edc_constants.constants import NO, NEW

from edc_action_item.site_action_items import site_action_items
from flourish_prn.action_items import CHILDOFF_STUDY_ACTION


class ChildFormValidatorMixin:

    infant_birth_model = None

    subject_consent_model = 'flourish_caregiver.subjectconsent'
    child_offstudy_model = 'flourish_prn.childoffstudy'
    consent_version_model = 'flourish_caregiver.flourishconsentversion'

    @property
    def infant_birth_cls(self):
        return django_apps.get_model(self.infant_birth_model)

    @property
    def subject_consent_cls(self):
        return django_apps.get_model(self.subject_consent_model)

    @property
    def consent_version_cls(self):
        return django_apps.get_model(self.consent_version_model)

    @property
    def child_offstudy_cls(self):
        return django_apps.get_model(self.child_offstudy_model)

    def clean(self):
        if self.cleaned_data.get('child_visit'):
            self.subject_identifier = self.cleaned_data.get(
                'child_visit').subject_identifier
            self.validate_against_visit_datetime(
                self.cleaned_data.get('report_datetime'))
        else:
            self.subject_identifier = self.cleaned_data.get('subject_identifier')

        self.validate_offstudy_model()
        super().clean()

    def validate_against_birth_date(self, infant_identifier=None,
                                    report_datetime=None):

        try:
            infant_birth = self.infant_birth_cls.objects.get(
                subject_identifier=infant_identifier)
        except self.infant_birth_cls.DoesNotExist:
            raise ValidationError(
                'Please complete Infant Birth form '
                f'before  proceeding.')
        else:
            if report_datetime and report_datetime < infant_birth.report_datetime:
                raise forms.ValidationError(
                    "Report datetime cannot be before enrollemt datetime.")
            else:
                return infant_birth

    def validate_against_visit_datetime(self, report_datetime):
        if report_datetime and report_datetime < \
                self.cleaned_data.get('child_visit').report_datetime:
            raise forms.ValidationError(
                "Report datetime cannot be before visit datetime.")

    def validate_against_visit_date(self, offstudy_date):
        if offstudy_date and offstudy_date < \
                self.cleaned_data.get('child_visit').report_datetime.date():
            raise forms.ValidationError({
                'offstudy_date':
                'offstudy date cannot be before visit date.'
            })

    def validate_offstudy_model(self):

        action_cls = site_action_items.get(
            self.child_offstudy_cls.action_name)
        action_item_model_cls = action_cls.action_item_model_cls()

        try:
            action_item_model_cls.objects.get(
                subject_identifier=self.subject_identifier,
                action_type__name=CHILDOFF_STUDY_ACTION,
                status=NEW)
        except action_item_model_cls.DoesNotExist:
            try:
                self.child_offstudy_cls.objects.get(
                    subject_identifier=self.subject_identifier)
            except self.child_offstudy_cls.DoesNotExist:
                pass
            else:
                raise forms.ValidationError(
                    'Participant has been taken offstudy. Cannot capture any '
                    'new data.')
        else:
            raise forms.ValidationError(
                'Participant is scheduled to be taken offstudy without '
                'any new data collection. Cannot capture any new data.')

    def validate_consent_version_obj(self, subject_identifier):

        latest_consent_obj = self.latest_consent_obj(subject_identifier)

        if latest_consent_obj:
            try:
                self.consent_version_cls.objects.get(
                    screening_identifier=latest_consent_obj.screening_identifier)
            except self.consent_version_cls.DoesNotExist:
                raise forms.ValidationError(
                    'Consent version form has not been completed, kindly complete it before'
                    ' continuing.')

    def latest_consent_obj(self, subject_identifier):

        subject_consents = self.subject_consent_cls.objects.filter(
            subject_identifier=subject_identifier[:-3])

        if subject_consents:
            return subject_consents.latest('consent_datetime')
