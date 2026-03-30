"""
Salesforce Metadata API — raw SOAP implementation.
No WSDL, no zeep, no CLI required.
Uses the OAuth access token directly as the SOAP session ID.
"""
import re
import logging
import requests

logger = logging.getLogger(__name__)

API_VERSION = "58.0"


# ---------------------------------------------------------------------------
# Low-level SOAP helpers
# ---------------------------------------------------------------------------

def _soap_envelope(session_id: str, body_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:met="http://soap.sforce.com/2006/04/metadata"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Header>
    <met:CallOptions>
      <met:client>SalesforceDataGenerator/1.0</met:client>
    </met:CallOptions>
    <met:SessionHeader>
      <met:sessionId>{session_id}</met:sessionId>
    </met:SessionHeader>
  </soapenv:Header>
  <soapenv:Body>
    {body_xml}
  </soapenv:Body>
</soapenv:Envelope>"""


def _metadata_endpoint(instance_url: str) -> str:
    return f"{instance_url.rstrip('/')}/services/Soap/m/{API_VERSION}"


def _post_soap(instance_url: str, session_id: str, soap_action: str, body_xml: str) -> requests.Response:
    envelope = _soap_envelope(session_id, body_xml)
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": soap_action,
    }
    url = _metadata_endpoint(instance_url)
    logger.debug(f"Metadata API POST → {url}  action={soap_action}")
    resp = requests.post(url, data=envelope.encode("utf-8"), headers=headers, timeout=60)
    return resp


def _parse_fault(xml_text: str) -> str:
    """Pull the faultstring out of a SOAP Fault response."""
    m = re.search(r"<faultstring[^>]*>(.*?)</faultstring>", xml_text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"<statusCode[^>]*>(.*?)</statusCode>", xml_text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return "Unknown Metadata API error"


def _check_result(xml_text: str) -> dict:
    """
    Parse the <result> block from a createMetadata / deleteMetadata response.
    Returns {"success": bool, "errors": [str]}
    """
    # success flag
    m = re.search(r"<success[^>]*>(true|false)</success>", xml_text, re.IGNORECASE)
    success = m and m.group(1).lower() == "true"

    errors = re.findall(r"<message[^>]*>(.*?)</message>", xml_text, re.DOTALL)
    errors += re.findall(r"<statusCode[^>]*>(.*?)</statusCode>", xml_text, re.DOTALL)
    errors = [e.strip() for e in errors if e.strip()]

    return {"success": success, "errors": errors}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _to_api_name(raw: str) -> str:
    """
    'My Object' → 'My_Object'
    'myObject'  → 'My_Object'
    Already has __c → stripped then reprocessed
    """
    raw = raw.replace("__c", "").strip()
    # Split camelCase
    raw = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw)
    words = re.split(r"[\s_\-]+", raw)
    return "_".join(w.capitalize() for w in words if w)


def _to_label(raw: str) -> str:
    api = _to_api_name(raw)
    return api.replace("_", " ")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_custom_object(
    instance_url: str,
    access_token: str,
    object_name: str,
    details: dict,
) -> dict:
    """
    Create a Salesforce custom object via the Metadata API (SOAP, no WSDL).

    Args:
        instance_url:  e.g. https://myorg.my.salesforce.com
        access_token:  OAuth bearer token
        object_name:   e.g. 'Treasure', 'Treasure__c', 'My Object'
        details:       optional dict with label, plural_label, name_field_label, sharing_model

    Returns:
        {"success": bool, "message": str, "api_name": str, "details": dict}
    """
    api_name_base = _to_api_name(object_name)
    full_name = f"{api_name_base}__c"
    label = details.get("label") or _to_label(object_name)
    plural_label = details.get("plural_label") or label + "s"
    name_field_label = details.get("name_field_label", "Name")
    sharing_model = details.get("sharing_model", "ReadWrite")
    description = details.get("description", "")

    desc_xml = f"<met:description>{description}</met:description>" if description else ""

    body = f"""<met:createMetadata>
      <met:metadata xsi:type="met:CustomObject">
        <met:fullName>{full_name}</met:fullName>
        <met:label>{label}</met:label>
        <met:pluralLabel>{plural_label}</met:pluralLabel>
        {desc_xml}
        <met:nameField>
          <met:label>{name_field_label}</met:label>
          <met:type>Text</met:type>
        </met:nameField>
        <met:deploymentStatus>Deployed</met:deploymentStatus>
        <met:sharingModel>{sharing_model}</met:sharingModel>
      </met:metadata>
    </met:createMetadata>"""

    try:
        resp = _post_soap(instance_url, access_token, "createMetadata", body)
        xml = resp.text

        if resp.status_code >= 500 or "<soapenv:Fault>" in xml or "<faultstring" in xml:
            fault = _parse_fault(xml)
            logger.error(f"Metadata API fault creating {full_name}: {fault}")
            return {
                "success": False,
                "action": "create_object",
                "api_name": full_name,
                "message": f"Metadata API error: {fault}",
                "details": details,
            }

        result = _check_result(xml)

        if result["success"]:
            logger.info(f"Successfully created custom object: {full_name}")
            return {
                "success": True,
                "action": "create_object",
                "api_name": full_name,
                "message": f"Custom object '{label}' ({full_name}) created successfully.",
                "details": {
                    "api_name": full_name,
                    "label": label,
                    "plural_label": plural_label,
                },
            }
        else:
            err_msg = "; ".join(result["errors"]) or "Unknown error"
            logger.error(f"Failed to create {full_name}: {err_msg}")
            return {
                "success": False,
                "action": "create_object",
                "api_name": full_name,
                "message": f"Failed to create object: {err_msg}",
                "details": details,
            }

    except Exception as exc:
        logger.exception(f"Exception creating custom object {full_name}")
        return {
            "success": False,
            "action": "create_object",
            "api_name": full_name,
            "message": f"Unexpected error: {str(exc)}",
            "details": details,
        }


def create_custom_field(
    instance_url: str,
    access_token: str,
    object_name: str,
    field_name: str,
    field_type: str = "Text",
    label: str = None,
    length: int = 255,
    required: bool = False,
    description: str = "",
) -> dict:
    """
    Create a custom field via Metadata API SOAP.
    This complements the Tooling API path for field creation.

    Args:
        object_name:  e.g. 'Account', 'Treasure__c'
        field_name:   e.g. 'Phone_Number'  (will get __c appended)
        field_type:   Text | Number | Email | Phone | Date | DateTime |
                      Checkbox | TextArea | LongTextArea | Picklist | Currency | Url
    """
    api_name_base = _to_api_name(field_name.replace("__c", ""))
    full_field = f"{object_name}.{api_name_base}__c"
    field_label = label or api_name_base.replace("_", " ")

    type_extras = ""
    if field_type in ("Text",):
        type_extras = f"<met:length>{length}</met:length>"
    elif field_type in ("LongTextArea", "Html"):
        type_extras = f"<met:length>{max(length, 32768)}</met:length><met:visibleLines>5</met:visibleLines>"
    elif field_type in ("Number", "Currency", "Percent"):
        type_extras = "<met:precision>18</met:precision><met:scale>2</met:scale>"

    required_xml = "<met:required>true</met:required>" if required else ""
    desc_xml = f"<met:description>{description}</met:description>" if description else ""

    body = f"""<met:createMetadata>
      <met:metadata xsi:type="met:CustomField">
        <met:fullName>{full_field}</met:fullName>
        <met:label>{field_label}</met:label>
        <met:type>{field_type}</met:type>
        {type_extras}
        {required_xml}
        {desc_xml}
      </met:metadata>
    </met:createMetadata>"""

    try:
        resp = _post_soap(instance_url, access_token, "createMetadata", body)
        xml = resp.text

        if resp.status_code >= 500 or "<soapenv:Fault>" in xml or "<faultstring" in xml:
            fault = _parse_fault(xml)
            return {"success": False, "message": f"Metadata API error: {fault}", "field": full_field}

        result = _check_result(xml)
        if result["success"]:
            return {"success": True, "message": f"Field '{field_label}' ({full_field}) created.", "field": full_field}
        else:
            err_msg = "; ".join(result["errors"]) or "Unknown error"
            return {"success": False, "message": f"Failed to create field: {err_msg}", "field": full_field}

    except Exception as exc:
        logger.exception(f"Exception creating field {full_field}")
        return {"success": False, "message": f"Unexpected error: {str(exc)}", "field": full_field}


def delete_custom_object(instance_url: str, access_token: str, object_name: str) -> dict:
    """Delete a custom object via Metadata API."""
    api_name = object_name if object_name.endswith("__c") else f"{_to_api_name(object_name)}__c"

    body = f"""<met:deleteMetadata>
      <met:type>CustomObject</met:type>
      <met:fullNames>{api_name}</met:fullNames>
    </met:deleteMetadata>"""

    try:
        resp = _post_soap(instance_url, access_token, "deleteMetadata", body)
        xml = resp.text

        if "<soapenv:Fault>" in xml or "<faultstring" in xml:
            return {"success": False, "message": _parse_fault(xml)}

        result = _check_result(xml)
        if result["success"]:
            return {"success": True, "message": f"Object {api_name} deleted."}
        else:
            return {"success": False, "message": "; ".join(result["errors"])}

    except Exception as exc:
        return {"success": False, "message": str(exc)}
