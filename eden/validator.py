# -*- coding: utf-8; -*-
import re

from bson import ObjectId
from eve.auth import auth_field_and_value
from eve.io.mongo import Validator
from eve.utils import config
from werkzeug.datastructures import FileStorage
import phonenumbers
from phonenumbers import carrier
from phonenumbers.phonenumberutil import number_type

import eden

ERROR_PATTERN = {'pattern': 1}
ERROR_UNIQUE = {'unique': 1}
ERROR_MINLENGTH = {'minlength': 1}
ERROR_REQUIRED = {'required': 1}
ERROR_JSON_LIST = {'json_list': 1}


class EdenValidator(Validator):

    def _validate_mapping(self, mapping, field, value):
        """ {'type': 'boolean'} """
        pass

    def _validate_index(self, field, value):
        """ {'type': 'boolean'} """
        pass

    def _validate_type_phone_number(self, value):
        """Enables validation for `phone_number` schema attribute.
        :param field: field name.
        :param value: field value.
        """
        try:
            return carrier._is_mobile(number_type(phonenumbers.parse(value)))
        except:
            return False

    def _validate_type_email(self, value):
        """Enables validation for `email` schema attribute.
        :param field: field name.
        :param value: field value.
        """
        regex = "^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@" \
                "(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+(?:\.[a-z0-9](?:[a-z0-9-]{0,4}[a-z0-9])?)*$"
        return re.match(regex, value, re.IGNORECASE)

    def _validate_type_file(self, value):
        """Enables validation for `file` schema attribute."""
        return isinstance(value, FileStorage)

    def _validate_multiple_emails(self, multiple, field, value):
        """ {'type': 'boolean'} """
        if multiple:
            emails = value.split(',')
            for email in emails:
                self._validate_type_email(field, email)

    def _set_id_query(self, query):
        if self._id:
            try:
                query[config.ID_FIELD] = {'$ne': ObjectId(self._id)}
            except:
                query[config.ID_FIELD] = {'$ne': self._id}

    def _validate_iunique(self, unique, field, value):
        """ {'type': 'boolean'} """

        if unique:
            pattern = '^{}$'.format(re.escape(value.strip()))
            query = {field: re.compile(pattern, re.IGNORECASE)}
            self._set_id_query(query)

            cursor = eden.get_resource_service(self.resource).get_from_mongo(req=None, lookup=query)
            if cursor.count():
                self._error(field, ERROR_UNIQUE)

    def _validate_iunique_per_parent(self, parent_field, field, value):
        """ {'type': 'boolean'} """
        original = self._original_document or {}
        update = self.document or {}

        parent_field_value = update.get(parent_field, original.get(parent_field))

        if parent_field:
            pattern = '^{}$'.format(re.escape(value.strip()))
            query = {
                field: re.compile(pattern, re.IGNORECASE),
                parent_field: parent_field_value
            }
            self._set_id_query(query)

            cursor = eden.get_resource_service(self.resource).get_from_mongo(req=None, lookup=query)
            if cursor.count():
                self._error(field, ERROR_UNIQUE)

    def _validate_required_fields(self, document):
        """ {'type': 'boolean'} """
        required = list(field for field, definition in self.schema.items()
                        if definition.get('required') is True)
        missing = set(required) - set(key for key in document.keys()
                                      if document.get(key) is not None or
                                      not self.ignore_none_values)
        for field in missing:
            self._error(field, ERROR_REQUIRED)

    def _validate_type_json_list(self, field, value):
        """It will fail later when loading."""
        if not isinstance(value, type('')):
            self._error(field, ERROR_JSON_LIST)

    def _validate_unique_template(self, unique, field, value):
        """ {'type': 'boolean'} """
        original = self._original_document or {}
        update = self.document or {}

        is_public = update.get('is_public', original.get('is_public', None))
        template_name = update.get('template_name', original.get('template_name', None))

        if is_public:
            query = {'is_public': True}
        else:
            _, auth_value = auth_field_and_value(self.resource)
            query = {'user': auth_value, 'is_public': False}

        query['template_name'] = re.compile('^{}$'.format(re.escape(template_name.strip())), re.IGNORECASE)

        if self._id:
            id_field = config.DOMAIN[self.resource]['id_field']
            query[id_field] = {'$ne': self._id}

        if eden.get_resource_service(self.resource).find_one(req=None, **query):
            self._error(field, "Template Name is not unique")
