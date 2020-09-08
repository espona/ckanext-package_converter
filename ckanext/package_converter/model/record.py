import sys

from lxml import etree
from lxml.etree import fromstring
from xmltodict import unparse, parse
import requests

import json
import six

from logging import getLogger

import logging

logging.basicConfig()

log = getLogger(__name__)


class Record(object):

    def __init__(self, metadata_format, content):
        self.metadata_format = metadata_format
        self.content = content

    def get_metadata_format(self):
        return self.metadata_format

    def get_content(self):
        return self.content

    def __repr__(self):
        return str(self)

    def __str__(self):
        return str(self).encode('utf-8')

    def __unicode__(self):
        return u'Record ({metadata_format}): {content}'.format(metadata_format=self.metadata_format,
                                                               content=self.content)


class XMLRecord(Record):

    def __init__(self, metadata_format, content):
        Record.__init__(self, metadata_format, content)
        self.xml_dict = parse(content)

    @classmethod
    def from_record(cls, record):
        return cls(record.get_metadata_format(), record.get_content())

    @classmethod
    def from_dict(cls, metadata_format, xml_dict):
        return cls(metadata_format, unparse(xml_dict, pretty=True))

    def get_xml_dict(self):
        return self.xml_dict

    def _get_dom(self, encoding):
        # encode xml content
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding=encoding)
        xml_dom = fromstring(self.content.encode(encoding), parser=parser)
        return xml_dom

    def validate(self, custom_xsd='', custom_replace=[], encoding='utf-8'):
        xml_dom = self._get_dom(encoding)

        if custom_xsd:
            xsd_content = custom_xsd
        else:
            xsd_url_str_orig = self.metadata_format.xsd_url
            log.debug("Validating against {0}".format(xsd_url_str_orig))

            # encode xsd_url string if necessary
            xsd_url_str = xsd_url_str_orig
            if isinstance(self.metadata_format.xsd_url, six.string_types):
                xsd_url_str = self.metadata_format.xsd_url.encode(encoding)
                log.debug("Encoded url {0}: '{1}'".format(encoding, xsd_url_str))

            # request XSD content
            res = requests.get(xsd_url_str)
            xsd_content = res.content

            # fix issues with included xsd's
            if custom_replace:
                for replace_pair in custom_replace:
                    xsd_content = xsd_content.replace(replace_pair[0], replace_pair[1])
            else:
                xsd_content = xsd_content.replace(b'schemaLocation="include/',
                                                  b'schemaLocation="'
                                                  + xsd_url_str_orig.rsplit("/", 1)[0].encode(encoding)
                                                  + b'/include/').replace(
                    b'xs:include schemaLocation="..',
                    b'xs:include schemaLocation="' + xsd_url_str_orig.rsplit("/", 2)[0].encode(encoding))

        doc_xsd = etree.XML(xsd_content)
        schema = etree.XMLSchema(doc_xsd)

        if schema.validate(xml_dom):
            return True
        else:
            log.info('Validation FAILED')
        try:
            validation = schema.assertValid(xml_dom)
            log.debug(validation)
        except etree.DocumentInvalid as e:
            log.warning('Document Invalid: {0}'.format(e))
        except:
            log.error('Exception: {0}'.format(sys.exc_info()[0]))
        return False

    def xsl_transform(self, xsl_path, encoding='utf-8'):
        xml_dom = self._get_dom(encoding)
        xsl_dom = etree.parse(xsl_path)
        transform = etree.XSLT(xsl_dom)
        new_dom = transform(xml_dom)
        return etree.tostring(new_dom, pretty_print=True)

    def __unicode__(self):
        return super(XMLRecord, self).__unicode__() + u' XML, {xml_dict}'.format(xml_dict=self.xml_dict)


class JSONRecord(Record):

    def __init__(self, metadata_format, json_dict):
        Record.__init__(self, metadata_format, json.dumps(json_dict, indent=4, ensure_ascii=False))
        self.json_dict = json_dict

    def get_json_dict(self):
        return self.json_dict

    @classmethod
    def from_record(cls, record):
        return cls(record.get_metadata_format(), json.loads(record.get_content()))

    def __unicode__(self):
        return super(JSONRecord, self).__unicode__() + u' JSON {json_dict}'.format(json_dict=self.json_dict)
