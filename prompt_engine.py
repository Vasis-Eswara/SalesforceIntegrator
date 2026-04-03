"""
Unified Prompt Engine for Salesforce Data Generator

Single entry point for ALL prompt processing across both:
  - Schema & Data Gen (/combined route)
  - Standalone Configure (/configure route)

Handles:
  - Metadata creation: objects, fields, validation rules, lookups
  - Data record generation: counts, relationships, ordering
  - Mixed prompts: metadata + data in one sentence
  - Relationship integrity validation
  - Deduplication and action ordering
"""
import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standard Salesforce object registry
# ---------------------------------------------------------------------------
STANDARD_OBJECTS = {
    'account', 'contact', 'lead', 'opportunity', 'case', 'user',
    'campaign', 'task', 'event', 'activity', 'product2', 'pricebook2',
    'pricebookentry', 'asset', 'contract', 'order', 'quote',
}

STANDARD_OBJECT_CANONICAL = {
    'account': 'Account', 'contact': 'Contact', 'lead': 'Lead',
    'opportunity': 'Opportunity', 'case': 'Case', 'user': 'User',
    'campaign': 'Campaign', 'task': 'Task', 'event': 'Event',
    'activity': 'Activity', 'product2': 'Product2', 'product': 'Product2',
    'pricebook2': 'Pricebook2', 'pricebook': 'Pricebook2',
    'pricebookentry': 'PricebookEntry', 'asset': 'Asset',
    'contract': 'Contract', 'order': 'Order', 'quote': 'Quote',
}

SKIP_TERMS = {
    'record', 'records', 'data', 'item', 'items', 'entry', 'entries',
    'owner', 'relationship', 'hierarchical', 'new', 'parent', 'following',
    'related', 'custom', 'object', 'objects', 'field', 'fields',
    'called', 'named', 'standard', 'sobject', 'the', 'a', 'an',
    'some', 'any', 'all', 'each', 'for', 'with',
    'and', 'or', 'to', 'from', 'in', 'on', 'at', 'of', 'by',
    'create', 'add', 'make', 'build', 'generate', 'insert',
    'type', 'value', 'detail', 'details', 'info',
}

# Action verbs that signal a sentence break (not a field name)
_ACTION_VERBS = {'generate', 'insert', 'create', 'add', 'make', 'build', 'delete', 'update'}

# ---------------------------------------------------------------------------
# Field type inference
# ---------------------------------------------------------------------------
FIELD_TYPE_KEYWORDS: Dict[str, List[str]] = {
    'email': ['email', 'mail', 'e_mail'],
    'phone': ['phone', 'mobile', 'tel', 'phonenumber', 'phone_number', 'fax'],
    'date': ['date', 'birthday', 'birth_date', 'dob', 'anniversary', 'hire_date',
             'start_date', 'end_date', 'expiry', 'expiration', 'due_date', 'close_date',
             'startdate', 'enddate'],
    'datetime': ['datetime', 'timestamp', 'created_at', 'updated_at', 'modified_at'],
    'currency': ['price', 'cost', 'amount', 'salary', 'revenue', 'fee', 'charge',
                 'budget', 'payment', 'total', 'subtotal', 'tax'],
    'percent': ['percent', 'percentage', 'rate', 'discount', 'commission'],
    'url': ['url', 'website', 'link', 'homepage', 'site'],
    'checkbox': ['active', 'enabled', 'flag', 'is_', 'has_', 'approved',
                 'verified', 'billable', 'taxable', 'complete', 'resolved'],
    'number': ['count', 'number', 'quantity', 'qty', 'age', 'pincode', 'pin',
               'zip', 'zipcode', 'rank', 'priority', 'sequence',
               'version', 'level', 'score', 'rating'],
    'textarea': ['description', 'comment', 'note', 'notes', 'detail',
                 'summary', 'body', 'content', 'bio', 'address'],
    'picklist': ['status', 'type', 'stage', 'category', 'industry',
                 'source', 'reason', 'department', 'region'],
}

SENSITIVE_FIELD_KEYWORDS = ['ssn', 'social_security', 'tax_id', 'ein', 'passport', 'license']

KNOWN_FIELD_TYPES = {
    'text', 'string', 'varchar', 'number', 'numeric', 'integer', 'int',
    'decimal', 'float', 'longtext', 'textarea', 'multiline', 'memo',
    'email', 'phone', 'tel', 'date', 'datetime', 'timestamp',
    'boolean', 'checkbox', 'bool', 'currency', 'money', 'percent',
    'percentage', 'url', 'link', 'picklist', 'dropdown', 'select',
    'lookup', 'reference', 'relation', 'master', 'master_detail', 'masterdetail',
}


def _infer_field_type(field_name: str) -> str:
    fn = field_name.lower().replace('__c', '').replace('_', ' ')
    for sf_type, keywords in FIELD_TYPE_KEYWORDS.items():
        if any(kw in fn for kw in keywords):
            return sf_type
    if any(kw in fn for kw in SENSITIVE_FIELD_KEYWORDS):
        return 'text'
    return 'text'


def _normalize_field_type(raw: str) -> str:
    mapping = {
        'text': 'text', 'string': 'text', 'varchar': 'text',
        'number': 'number', 'numeric': 'number', 'integer': 'number',
        'int': 'number', 'decimal': 'number', 'float': 'number',
        'longtext': 'textarea', 'long text': 'textarea', 'textarea': 'textarea',
        'multiline': 'textarea', 'memo': 'textarea',
        'email': 'email', 'phone': 'phone', 'tel': 'phone',
        'date': 'date', 'datetime': 'datetime', 'timestamp': 'datetime',
        'boolean': 'checkbox', 'checkbox': 'checkbox', 'bool': 'checkbox',
        'currency': 'currency', 'money': 'currency',
        'percent': 'percent', 'percentage': 'percent',
        'url': 'url', 'link': 'url',
        'picklist': 'picklist', 'dropdown': 'picklist', 'select': 'picklist',
        'lookup': 'lookup', 'reference': 'lookup', 'relation': 'lookup',
        'master': 'master_detail', 'master_detail': 'master_detail',
        'masterdetail': 'master_detail',
    }
    return mapping.get(raw.lower().strip(), 'text')


def _normalize_object_name(raw: str) -> str:
    """Convert raw object name text to a Salesforce API name."""
    raw = raw.strip().rstrip('.,;:')
    # Strip trailing "object" word if present
    raw = re.sub(r'\s+object\s*$', '', raw, flags=re.IGNORECASE).strip()
    canonical = STANDARD_OBJECT_CANONICAL.get(raw.lower())
    if canonical:
        return canonical
    if raw.endswith('__c'):
        return raw
    parts = re.split(r'[\s\-]+', raw)
    name = '_'.join(p.capitalize() for p in parts if p)
    return name + '__c'


def _field_api_name(label: str) -> str:
    """Convert a field label/name to a Salesforce API name ending in __c."""
    # Strip type hints that may be appended (e.g. "Name -- text")
    label = re.split(r'\s*--\s*|\s*:\s*|\s*\(', label)[0].strip()
    cleaned = re.sub(r'[^a-zA-Z0-9\s_]', '', label).strip()
    parts = re.split(r'[\s_]+', cleaned)
    name = '_'.join(p.capitalize() for p in parts if p)
    if not name.endswith('__c'):
        name += '__c'
    return name


def _field_label(api_name: str) -> str:
    base = api_name.replace('__c', '').replace('_', ' ')
    return base.title()


def _build_field_details(api_name: str, field_type: str, extra: Optional[Dict] = None) -> Dict:
    label = _field_label(api_name)
    details: Dict[str, Any] = {
        'api_name': api_name,
        'label': label,
        'description': f'{label} field',
        'required': False,
        'unique': False,
        'type': field_type,
    }
    defaults: Dict[str, Dict] = {
        'text': {'length': 255},
        'textarea': {'length': 32768, 'visible_lines': 3},
        'number': {'precision': 18, 'scale': 0},
        'currency': {'precision': 18, 'scale': 2},
        'percent': {'precision': 5, 'scale': 2},
        'email': {}, 'phone': {}, 'url': {'length': 255},
        'date': {}, 'datetime': {},
        'checkbox': {'default_value': False},
        'picklist': {'picklist_values': _default_picklist_values(label)},
        'lookup': {}, 'master_detail': {},
    }
    details.update(defaults.get(field_type, {}))
    if extra:
        details.update(extra)
    return details


def _default_picklist_values(label: str) -> List[str]:
    ll = label.lower()
    if 'status' in ll:
        return ['Active', 'Inactive', 'Pending', 'Draft']
    if 'priority' in ll:
        return ['Low', 'Medium', 'High', 'Critical']
    if 'stage' in ll:
        return ['Prospecting', 'Qualification', 'Proposal', 'Closed Won', 'Closed Lost']
    if 'type' in ll:
        return ['Type A', 'Type B', 'Type C']
    if 'industry' in ll:
        return ['Technology', 'Finance', 'Healthcare', 'Manufacturing', 'Retail']
    return ['Option 1', 'Option 2', 'Option 3']


def _build_object_details(raw_name: str, api_name: str) -> Dict:
    label = raw_name.replace('_', ' ').replace('__c', '').strip().title()
    return {
        'api_name': api_name,
        'label': label,
        'plural_label': label + 's',
        'description': f'Custom object for {label.lower()} management',
        'deployment_status': 'Deployed',
        'sharing_model': 'ReadWrite',
    }


# ---------------------------------------------------------------------------
# Helpers for parsing field lists
# ---------------------------------------------------------------------------

def _is_likely_sentence_fragment(text: str) -> bool:
    """Return True if this text looks like a sentence/command, not a field name."""
    text_lower = text.lower().strip()
    # Has digits (like "generate 20 records")
    if re.search(r'\d', text):
        return True
    # Starts with a verb
    first_word = text_lower.split()[0] if text_lower.split() else ''
    if first_word in _ACTION_VERBS:
        return True
    # Too long to be a field name
    if len(text.split()) > 5:
        return True
    return False


def _split_field_list(text: str) -> List[str]:
    """Split a field list string into individual field names/specs."""
    # Truncate at obvious sentence breaks ("and generate", "then", ".")
    text = re.split(r'\s+and\s+(?:generate|insert|create|then)\b', text, flags=re.IGNORECASE)[0]
    # Stop at sentence end only when period follows a lowercase letter (not a digit/list item)
    text = re.split(r'(?<=[a-z])\.\s+[A-Z]', text)[0]
    text = text.strip()

    # Numbered lists: "1. Name 2. Email"
    numbered = re.findall(r'\d+[.)]\s*([a-zA-Z][a-zA-Z0-9_\s\-]*?)(?=\s*\d+[.)]|$)', text)
    if numbered:
        result = [n.strip().rstrip('.,;') for n in numbered if n.strip()]
        return [r for r in result if not _is_likely_sentence_fragment(r)]

    # Split by comma and "and"
    parts = re.split(r',\s*|\s+and\s+', text)
    result = []
    for part in parts:
        part = part.strip().rstrip('.,;')
        part = re.sub(r'^(?:and|or|the|a|an)\s+', '', part, flags=re.IGNORECASE).strip()
        if part and len(part) > 1 and part.lower() not in SKIP_TERMS:
            if not _is_likely_sentence_fragment(part):
                result.append(part)
    return result


def _split_name_list(text: str) -> List[str]:
    text = re.sub(r'\band\b|\bor\b', ',', text, flags=re.IGNORECASE)
    return [n.strip().rstrip('.,;') for n in text.split(',') if n.strip()]


def _parse_typed_field(spec: str) -> Tuple[str, Optional[Dict]]:
    """Parse a field spec that may include a type hint."""
    patterns = [
        re.compile(r'.+?\s*--\s*([a-zA-Z_]+)'),
        re.compile(r'.+?\s*\(\s*([a-zA-Z_]+)\s*\)'),
        re.compile(r'.+?\s*:\s*([a-zA-Z_]+)$'),
        re.compile(r'.+?\s+-\s+([a-zA-Z_]+)$'),
    ]
    for pat in patterns:
        m = pat.match(spec.strip())
        if m:
            type_word = m.group(1).lower()
            if type_word in KNOWN_FIELD_TYPES:
                return _normalize_field_type(type_word), None
    return _infer_field_type(spec), None


def _extract_number_constraints(text: str) -> Optional[Dict]:
    m = re.search(r'from\s+(\d+)\s+to\s+(\d+)', text, re.IGNORECASE)
    if m:
        result: Dict[str, Any] = {'min_value': m.group(1), 'max_value': m.group(2)}
        d = re.search(r'default(?:\s+value(?:\s+of)?)?\s+(\d+)', text, re.IGNORECASE)
        if d:
            result['default_value'] = d.group(1)
        return result
    return None


# ---------------------------------------------------------------------------
# Metadata parser — multi-pass accumulator
# ---------------------------------------------------------------------------

def _parse_metadata_actions(prompt: str, existing_objects: List[str] = None) -> List[Dict]:
    """Run all metadata parsers and accumulate every matching action (no elif)."""
    existing_objects = existing_objects or []
    actions: List[Dict] = []
    seen_objects: set = set()
    seen_fields: set = set()

    def add_object(raw_name: str, api_name: str):
        if api_name.lower() not in seen_objects:
            seen_objects.add(api_name.lower())
            actions.append({
                'type': 'create_object',
                'target': {'object': api_name},
                'details': _build_object_details(raw_name, api_name),
            })

    def add_field(obj_api: str, field_api: str, field_type: str, extra: Optional[Dict] = None):
        key = (obj_api.lower(), field_api.lower())
        if key not in seen_fields:
            seen_fields.add(key)
            actions.append({
                'type': 'create_field',
                'target': {'object': obj_api, 'field': field_api},
                'details': _build_field_details(field_api, field_type, extra),
            })

    def add_validation(obj_api: str, rule_name: str, condition: str, message: str):
        actions.append({
            'type': 'create_validation_rule',
            'target': {'object': obj_api, 'rule': rule_name},
            'details': {
                'name': rule_name,
                'description': f'Validation rule: {rule_name}',
                'error_condition': condition,
                'error_message': message,
                'active': True,
            }
        })

    p = prompt.strip()

    # -----------------------------------------------------------------------
    # PASS A: Object + fields in one sentence
    # Handles:
    #   "Create a Project object with fields Name, Start Date, Budget"
    #   "Create a custom object called Project with fields Name, Budget"
    #   "Build an Employee custom object with fields: Name, Department, Salary"
    # -----------------------------------------------------------------------

    # Form 1: "<Name> object with fields <list>"
    obj_with_fields_pat1 = re.compile(
        r'(?:create|make|build)\s+(?:a\s+|an\s+|the\s+)?(?:custom\s+)?'
        r'([a-zA-Z][a-zA-Z0-9_\s]{0,50}?)\s+(?:custom\s+)?object\s+'
        r'with\s+(?:the\s+)?(?:following\s+)?fields?\s*:?\s+(.+)',
        re.IGNORECASE | re.DOTALL,
    )

    # Form 2: "object called/named <Name> with fields <list>"
    obj_with_fields_pat2 = re.compile(
        r'(?:create|make|build)\s+(?:a\s+|an\s+|the\s+)?(?:custom\s+)?object\s+'
        r'(?:called|named)\s+["\']?([a-zA-Z][a-zA-Z0-9_\s]{0,60})["\']?\s+'
        r'with\s+(?:the\s+)?(?:following\s+)?fields?\s*:?\s+(.+)',
        re.IGNORECASE | re.DOTALL,
    )

    for pat in (obj_with_fields_pat1, obj_with_fields_pat2):
        for m in pat.finditer(p):
            raw_obj = m.group(1).strip().rstrip('.,;:')
            # Strip trailing "object" word
            raw_obj = re.sub(r'\s+object\s*$', '', raw_obj, flags=re.IGNORECASE).strip()
            if raw_obj.lower() in SKIP_TERMS or len(raw_obj) < 2:
                continue
            obj_api = _normalize_object_name(raw_obj)
            add_object(raw_obj, obj_api)
            field_text = m.group(2).strip()
            for fname in _split_field_list(field_text):
                ftype, extra = _parse_typed_field(fname)
                fapi = _field_api_name(fname)
                add_field(obj_api, fapi, ftype, extra)

    # -----------------------------------------------------------------------
    # PASS B: Field list for an existing or new object
    # Handles:
    #   "Add fields Email, Phone, DOB to the Contact object"
    #   "Create the following fields under Treasure: 1. Name -- text ..."
    #   "Contact object needs fields: Email, Phone"
    # -----------------------------------------------------------------------
    fields_to_obj_patterns = [
        # "add/create fields <list> to/under/on <Object>"
        re.compile(
            r'(?:add|create|make)\s+(?:the\s+)?(?:following\s+)?(?:custom\s+)?fields?\s+'
            r'(.+?)\s+(?:to|under|on|in|for)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?'
            r'([a-zA-Z][a-zA-Z0-9_\s]{1,60})(?=\s*(?:$|[.,;!?\n]))',
            re.IGNORECASE,
        ),
        # "create/add fields under/to/on <Object>: <list>"  ← colon separator
        re.compile(
            r'(?:create|add|make)\s+(?:the\s+)?(?:following\s+)?(?:custom\s+)?fields?\s+'
            r'(?:under|to|on|in|for)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?'
            r'([a-zA-Z][a-zA-Z0-9_\s]{1,60})\s*:\s*(.+)',
            re.IGNORECASE | re.DOTALL,
        ),
        # "<Object> needs/requires fields: <list>"
        re.compile(
            r'([a-zA-Z][a-zA-Z0-9_\s]{1,60}?)\s+(?:needs|requires|should have|must have)\s+'
            r'(?:the\s+)?(?:following\s+)?(?:custom\s+)?fields?\s*:?\s+(.+)',
            re.IGNORECASE | re.DOTALL,
        ),
        # "for/under/on <Object> add/create fields: <list>"
        re.compile(
            r'(?:for|on|under)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?'
            r'([a-zA-Z][a-zA-Z0-9_\s]{1,60}?)\s+(?:create|add|make)\s+'
            r'(?:the\s+)?(?:following\s+)?(?:custom\s+)?fields?\s*:?\s*(.+)',
            re.IGNORECASE | re.DOTALL,
        ),
    ]
    for i, pat in enumerate(fields_to_obj_patterns):
        for m in pat.finditer(p):
            g1, g2 = m.group(1).strip(), m.group(2).strip()
            # Determine which group is object vs field list
            # If g1 contains commas and g2 doesn't, g1 is the field list
            if ',' in g1 and ',' not in g2 and i == 0:
                field_text, raw_obj = g1, g2
            else:
                raw_obj, field_text = g1, g2

            raw_obj = raw_obj.strip().rstrip('.,;:')
            raw_obj = re.sub(r'\s+object\s*$', '', raw_obj, flags=re.IGNORECASE).strip()
            if raw_obj.lower() in SKIP_TERMS or len(raw_obj) < 2:
                continue
            obj_api = _normalize_object_name(raw_obj)
            for fname in _split_field_list(field_text):
                ftype, extra = _parse_typed_field(fname)
                fapi = _field_api_name(fname)
                add_field(obj_api, fapi, ftype, extra)

    # -----------------------------------------------------------------------
    # PASS C: Single-field creation
    # Handles:
    #   "Add a custom field called Rating to the Account object"
    #   "Create a Phone field on the Contact object"
    #   "Add an Email field called Work Email to Lead"
    # -----------------------------------------------------------------------
    # Pattern 1: "add/create a [type] field called/named <name> to/on <Object>"
    sfp1 = re.compile(
        r'(?:add|create|make)\s+(?:a\s+|an\s+)?(?:custom\s+)?'
        r'(?:(text|number|email|phone|date|datetime|currency|percent|url|checkbox|picklist|textarea|lookup)\s+)?'
        r'field\s+(?:called|named)\s+'
        r'["\']?([a-zA-Z][a-zA-Z0-9_\s]{0,60}?)["\']?\s+'
        r'(?:to|on|in|under|for)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?'
        r'([a-zA-Z][a-zA-Z0-9_\s]{1,60})',
        re.IGNORECASE,
    )
    # Pattern 2: "add/create a <name> <type> field to/on <Object>"
    sfp2 = re.compile(
        r'(?:add|create|make)\s+(?:a\s+|an\s+)?(?:custom\s+)?'
        r'([a-zA-Z][a-zA-Z0-9_\s]{1,40}?)\s+'
        r'(text|number|email|phone|date|datetime|currency|percent|url|checkbox|picklist|textarea|lookup)\s+field\s+'
        r'(?:to|on|in|under|for)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?'
        r'([a-zA-Z][a-zA-Z0-9_\s]{1,60})',
        re.IGNORECASE,
    )
    # Pattern 3: "add <name> field to <Object>"
    sfp3 = re.compile(
        r'(?:add|create)\s+(?:a\s+|an\s+)?([a-zA-Z][a-zA-Z0-9_\s]{1,40}?)\s+field\s+'
        r'(?:to|on|in)\s+(?:the\s+)?(?:custom\s+)?(?:object\s+)?'
        r'([a-zA-Z][a-zA-Z0-9_\s]{1,60})',
        re.IGNORECASE,
    )
    for m in sfp1.finditer(p):
        ftype_raw, fname_raw, obj_raw = [g.strip() if g else '' for g in m.groups()]
        ftype = _normalize_field_type(ftype_raw) if ftype_raw else _infer_field_type(fname_raw)
        fapi = _field_api_name(fname_raw)
        obj_api = _normalize_object_name(obj_raw)
        extra = _extract_number_constraints(p)
        add_field(obj_api, fapi, ftype, extra or None)

    for m in sfp2.finditer(p):
        fname_raw, ftype_raw, obj_raw = [g.strip() for g in m.groups()]
        ftype = _normalize_field_type(ftype_raw)
        fapi = _field_api_name(fname_raw)
        obj_api = _normalize_object_name(obj_raw)
        add_field(obj_api, fapi, ftype)

    for m in sfp3.finditer(p):
        fname_raw, obj_raw = [g.strip() for g in m.groups()]
        ftype = _infer_field_type(fname_raw)
        fapi = _field_api_name(fname_raw)
        obj_api = _normalize_object_name(obj_raw)
        add_field(obj_api, fapi, ftype)

    # -----------------------------------------------------------------------
    # PASS D: Multiple object creation
    # Handles: "Create objects Invoice, Payment, LineItem"
    # -----------------------------------------------------------------------
    multi_obj_pat = re.compile(
        r'(?:create|make|build|add)\s+(?:the\s+)?(?:custom\s+)?objects?\s+'
        r'(?:(?:called|named|for)\s+)?([a-zA-Z][a-zA-Z0-9_,\s\-]{1,200})',
        re.IGNORECASE,
    )
    for m in multi_obj_pat.finditer(p):
        objects_text = m.group(1).strip()
        # Trim at "with fields" or "and generate" etc.
        objects_text = re.split(r'\s+with\s+fields?\b|\s+and\s+generate\b|\s+then\b', objects_text, flags=re.IGNORECASE)[0]
        obj_names = _split_name_list(objects_text)
        for raw in obj_names:
            raw = raw.strip().rstrip('.,;')
            if raw.lower() in SKIP_TERMS or len(raw) < 2:
                continue
            if re.search(r'\b(text|number|email|phone|date|currency)\b', raw, re.IGNORECASE):
                continue
            obj_api = _normalize_object_name(raw)
            add_object(raw, obj_api)

    # -----------------------------------------------------------------------
    # PASS E: Standalone single object (no fields)
    # Handles: "Create a custom object called Treasure"
    # Uses lazy quantifiers and stop-at-preposition anchors to avoid
    # over-capturing into following clauses ("with fields ...", etc.)
    # -----------------------------------------------------------------------
    single_obj_patterns = [
        # "create object called/named <Name>" — stop before "with", end, or punctuation
        re.compile(
            r'(?:create|make|build|add)\s+(?:a\s+|an\s+|the\s+)?(?:custom\s+)?object\s+'
            r'(?:called|named)\s+["\']?([a-zA-Z][a-zA-Z0-9_\s]{0,40}?)["\']?'
            r'(?=\s+with\b|\s*$|\s*[.,;!?\n])',
            re.IGNORECASE,
        ),
        # "create a <Name> object" — single-word only (no spaces), stops ambiguity
        re.compile(
            r'(?:create|make|build|add)\s+(?:a\s+|an\s+|the\s+)?(?:custom\s+)?'
            r'([a-zA-Z][a-zA-Z0-9_]{1,60})\s+(?:custom\s+)?object\b'
            r'(?!\s+called|\s+named)',
            re.IGNORECASE,
        ),
        # "new custom object called/named <Name>"
        re.compile(
            r'new\s+(?:custom\s+)?object\s+(?:called|named)\s+["\']?([a-zA-Z][a-zA-Z0-9_\s]{0,40}?)["\']?'
            r'(?=\s+with\b|\s*$|\s*[.,;!?\n])',
            re.IGNORECASE,
        ),
    ]
    for pat in single_obj_patterns:
        for m in pat.finditer(p):
            raw = m.group(1).strip().rstrip('.,;:')
            raw = re.sub(r'\s+object\s*$', '', raw, flags=re.IGNORECASE).strip()
            if raw.lower() in SKIP_TERMS or len(raw) < 2:
                continue
            obj_api = _normalize_object_name(raw)
            add_object(raw, obj_api)

    # -----------------------------------------------------------------------
    # PASS F: Lookup / master-detail relationship field
    # Handles: "Add a lookup from Contact to Account"
    # -----------------------------------------------------------------------
    lookup_pat = re.compile(
        r'(?:add|create)\s+(?:a\s+)?(?:lookup|master.?detail|relationship)\s+'
        r'(?:field\s+)?(?:from|between)\s+([a-zA-Z][a-zA-Z0-9_\s]{0,60}?)\s+'
        r'(?:to|and)\s+([a-zA-Z][a-zA-Z0-9_\s]{0,60})',
        re.IGNORECASE,
    )
    for m in lookup_pat.finditer(p):
        child_raw, parent_raw = m.group(1).strip(), m.group(2).strip()
        child_api = _normalize_object_name(child_raw)
        parent_api = _normalize_object_name(parent_raw)
        parent_base = parent_api.replace('__c', '')
        fapi = f'{parent_base}__c'
        add_field(child_api, fapi, 'lookup', {'reference_to': parent_api})

    # -----------------------------------------------------------------------
    # PASS G: Validation rules
    # Handles: "Add a validation rule on Contact to ensure Email is not blank"
    # -----------------------------------------------------------------------
    val_pat = re.compile(
        r'(?:add|create|make)\s+(?:a\s+)?validation\s+rule\s+'
        r'(?:on|for|to)\s+(?:the\s+)?(?:object\s+)?'
        r'([a-zA-Z][a-zA-Z0-9_]{1,60})\s+'   # object name — no spaces allowed (avoids runaway)
        r'(?:to|that|:)?\s*(.{5,200})',
        re.IGNORECASE,
    )
    for m in val_pat.finditer(p):
        obj_raw = m.group(1).strip()
        condition_text = m.group(2).strip()
        obj_api = _normalize_object_name(obj_raw)
        rule_name = re.sub(r'\W+', '_', condition_text[:40]).strip('_') or 'Custom_Rule'
        add_validation(obj_api, rule_name, '/* Define condition */', condition_text[:200])

    # -----------------------------------------------------------------------
    # Validate: only drop field actions for objects being created in THIS batch
    # that weren't found in the batch itself.
    # Fields targeting EXISTING org objects or unknown custom objects are kept —
    # Salesforce API will return a clear error if the object truly doesn't exist.
    # -----------------------------------------------------------------------
    created_obj_apis = {a['target']['object'].lower() for a in actions if a['type'] == 'create_object'}
    existing_lower = {o.lower() for o in existing_objects}
    standard_lower = {v.lower() for v in STANDARD_OBJECT_CANONICAL.values()}
    all_known = created_obj_apis | existing_lower | standard_lower

    validated: List[Dict] = []
    orphaned: set = set()
    for action in actions:
        if action['type'] == 'create_field' and created_obj_apis:
            # Only enforce validation when we ARE creating objects in this batch
            # (so we can catch obvious cross-reference errors)
            obj = action['target']['object'].lower()
            if obj not in all_known:
                orphaned.add(action['target']['object'])
                logger.warning(f"Field target '{action['target']['object']}' not in created/known objects")
                # Still include it — object might exist in org already
        validated.append(action)

    # Order: objects first, then fields, then validation rules
    order = {'create_object': 0, 'create_field': 1, 'create_validation_rule': 2}
    validated.sort(key=lambda a: order.get(a['type'], 9))

    return validated


# ---------------------------------------------------------------------------
# Data record parser
# ---------------------------------------------------------------------------

def _depluralize(word: str) -> str:
    """Simple English de-pluralisation."""
    if word.endswith('ies') and len(word) > 4:
        return word[:-3] + 'y'
    if word.endswith('ses') or word.endswith('zes') or word.endswith('xes'):
        return word[:-2]
    if word.endswith('s') and len(word) > 3 and not word.endswith('ss'):
        return word[:-1]
    return word


def _data_normalize_object(raw: str) -> Optional[str]:
    """Normalise a raw token to a Salesforce object API name."""
    raw = raw.strip()
    if raw.lower() in SKIP_TERMS:
        return None
    # Try canonical first (handles 'opportunities' → 'Opportunity' if present)
    canonical = STANDARD_OBJECT_CANONICAL.get(raw.lower())
    if canonical:
        return canonical
    # Try depluralized form
    dep = _depluralize(raw)
    canonical = STANDARD_OBJECT_CANONICAL.get(dep.lower())
    if canonical:
        return canonical
    if len(raw) < 2:
        return None
    # Return capitalised
    return dep[0].upper() + dep[1:]


def _parse_data_actions(prompt: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'objects': {},
        'relationships': [],
        'execution_order': [],
        'warnings': [],
    }

    def add_data_object(api_name: str, count: int):
        if not api_name or api_name.lower() in SKIP_TERMS:
            return
        if api_name in result['objects']:
            if count > 1:
                result['objects'][api_name]['count'] = max(result['objects'][api_name]['count'], count)
        else:
            result['objects'][api_name] = {
                'count': count,
                'api_name': api_name,
                'label': _create_label(api_name),
                'fields': {},
                'children': [],
            }

    # Explicit count patterns
    count_patterns = [
        re.compile(r'(?:create|generate|insert|make|add)\s+(\d+)\s+([a-zA-Z][a-zA-Z0-9_]*)', re.IGNORECASE),
        re.compile(r'(\d+)\s+records?\s+(?:for|of|in)\s+([a-zA-Z][a-zA-Z0-9_]*)', re.IGNORECASE),
        re.compile(r'([a-zA-Z][a-zA-Z0-9_]+)\s*\((\d+)\)', re.IGNORECASE),
        re.compile(r'\b(\d+)\s+([A-Z][a-zA-Z0-9_]+)s?\b'),
    ]
    for pat in count_patterns:
        for m in pat.finditer(prompt):
            g = m.groups()
            if g[0].isdigit():
                count, raw_name = int(g[0]), g[1]
            else:
                raw_name, count = g[0], int(g[1])
            if raw_name.lower() in SKIP_TERMS:
                continue
            api_name = _data_normalize_object(raw_name)
            if api_name:
                add_data_object(api_name, count)

    # Relationship patterns
    rel_patterns = [
        re.compile(
            r'each\s+([a-zA-Z][a-zA-Z0-9_]*)\s+(?:should\s+)?(?:have|contain|include|has)\s+(\d+)\s+([a-zA-Z][a-zA-Z0-9_]*)',
            re.IGNORECASE,
        ),
        re.compile(
            r'(\d+)\s+([a-zA-Z][a-zA-Z0-9_]+)s?\s+(?:per|for|linked to)\s+each\s+([a-zA-Z][a-zA-Z0-9_]*)',
            re.IGNORECASE,
        ),
        re.compile(
            r'link\s+(?:each\s+)?([a-zA-Z][a-zA-Z0-9_]*)\s+to\s+(?:a\s+|an\s+)?([a-zA-Z][a-zA-Z0-9_]*)',
            re.IGNORECASE,
        ),
        re.compile(
            r'([a-zA-Z][a-zA-Z0-9_]+)s?\s+linked\s+to\s+(?:each\s+)?([a-zA-Z][a-zA-Z0-9_]*)',
            re.IGNORECASE,
        ),
        re.compile(
            r'([a-zA-Z][a-zA-Z0-9_]+)s?\s+(?:should\s+)?belong\s+to\s+([a-zA-Z][a-zA-Z0-9_]+)',
            re.IGNORECASE,
        ),
    ]
    for i, pat in enumerate(rel_patterns):
        for m in pat.finditer(prompt):
            g = m.groups()
            try:
                if i == 0:
                    parent = _data_normalize_object(g[0])
                    count = int(g[1])
                    child = _data_normalize_object(g[2])
                elif i == 1:
                    count = int(g[0])
                    child = _data_normalize_object(g[1])
                    parent = _data_normalize_object(g[2])
                else:
                    child = _data_normalize_object(g[0])
                    parent = _data_normalize_object(g[1])
                    count = 1
                if not parent or not child or parent in SKIP_TERMS or child in SKIP_TERMS:
                    continue
                result['relationships'].append({
                    'parent': parent, 'child': child, 'count': count,
                    'field_name': f'{parent}Id' if not parent.endswith('__c') else f'{parent[:-3]}__c',
                })
                add_data_object(parent, 1)
                add_data_object(child, count)
            except Exception:
                continue

    # Adjust child counts by relationship multiplier
    for rel in result['relationships']:
        parent, child, rc = rel['parent'], rel['child'], rel['count']
        if parent in result['objects'] and child in result['objects'] and rc > 1:
            pc = result['objects'][parent]['count']
            result['objects'][child]['count'] = max(result['objects'][child]['count'], pc * rc)

    _calculate_execution_order(result)
    return result


def _calculate_execution_order(result: Dict):
    objects = set(result['objects'].keys())
    deps: Dict[str, set] = {o: set() for o in objects}
    for rel in result['relationships']:
        if rel['child'] in deps:
            deps[rel['child']].add(rel['parent'])

    ordered: List[str] = []
    remaining = objects.copy()
    while remaining:
        ready = [o for o in remaining if not deps[o] or deps[o].issubset(set(ordered))]
        if not ready:
            ready = sorted(remaining)
            result['warnings'].append(
                f"Potential circular dependency detected. Using alphabetical order: {', '.join(ready)}"
            )
            ordered.extend(ready)
            break
        for o in sorted(ready):
            ordered.append(o)
            remaining.remove(o)
    result['execution_order'] = ordered


def _create_label(api_name: str) -> str:
    base = api_name[:-3] if api_name.endswith('__c') else api_name
    return re.sub(r'([A-Z])', r' \1', base).strip()


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

METADATA_KEYWORDS = {
    'object', 'objects', 'field', 'fields', 'custom object', 'custom field',
    'validation rule', 'lookup', 'master-detail', 'master detail',
    'schema', 'sobject',
}

DATA_KEYWORDS = {
    'generate', 'insert', 'records', 'populate',
    'bulk', 'seed', 'fill', 'load', 'fake', 'test data',
}


def _classify_intent(prompt: str) -> Dict[str, bool]:
    pl = prompt.lower()
    has_metadata = any(kw in pl for kw in METADATA_KEYWORDS)
    has_data = any(kw in pl for kw in DATA_KEYWORDS)

    has_count = bool(re.search(r'\b\d+\b', prompt))

    # Explicit data generation verbs with counts
    if re.search(r'(?:generate|insert)\s+\d+', pl):
        has_data = True

    # "create N <Object>" pattern strongly implies data when N > 0
    if re.search(r'(?:create|make|add)\s+\d+\s+[a-zA-Z]', pl) and not has_metadata:
        has_data = True

    # If metadata keywords present but also has "generate N" → mixed
    # If only count present without metadata keywords → data only
    if has_count and not has_metadata and not has_data:
        has_data = True

    return {'metadata': has_metadata, 'data': has_data, 'mixed': has_metadata and has_data}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_prompt(prompt: str, existing_objects: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Single entry point for ALL prompt analysis.

    Returns:
        {
          'intent': {'metadata': bool, 'data': bool, 'mixed': bool},
          'metadata_actions': [...],
          'data_plan': {...},
          'warnings': [...],
          'errors': [...],
          'prompt': original_prompt,
        }
    """
    if not prompt or not prompt.strip():
        return {
            'intent': {'metadata': False, 'data': False, 'mixed': False},
            'metadata_actions': [], 'data_plan': {},
            'warnings': [], 'errors': ['Empty prompt provided.'],
            'prompt': prompt or '',
        }

    existing_objects = existing_objects or []
    warnings: List[str] = []
    errors: List[str] = []

    try:
        intent = _classify_intent(prompt)
        logger.info(f"Intent: {intent} for prompt: {prompt[:80]!r}")

        metadata_actions: List[Dict] = []
        data_plan: Dict = {}

        if intent['metadata']:
            try:
                metadata_actions = _parse_metadata_actions(prompt, existing_objects)
                logger.info(f"Parsed {len(metadata_actions)} metadata actions")
            except Exception as e:
                logger.error(f"Metadata parse error: {e}", exc_info=True)
                errors.append(f"Metadata parsing error: {e}")

        if intent['data']:
            try:
                data_plan = _parse_data_actions(prompt)
                logger.info(f"Parsed data plan: {list(data_plan.get('objects', {}).keys())}")
                warnings.extend(data_plan.pop('warnings', []))
            except Exception as e:
                logger.error(f"Data parse error: {e}", exc_info=True)
                errors.append(f"Data parsing error: {e}")

        if not metadata_actions and not data_plan.get('objects'):
            errors.append(
                "Could not parse any actions from this prompt. Try being more specific, e.g.:\n"
                "• 'Create a custom object called Project with fields Name, Start Date, Budget'\n"
                "• 'Add fields Email, Phone to the Contact object'\n"
                "• 'Generate 10 Accounts and 5 Contacts linked to each Account'"
            )

        return {
            'intent': intent,
            'metadata_actions': metadata_actions,
            'data_plan': data_plan,
            'warnings': warnings,
            'errors': errors,
            'prompt': prompt,
        }

    except Exception as e:
        logger.error(f"Prompt engine error: {e}", exc_info=True)
        return {
            'intent': {'metadata': False, 'data': False, 'mixed': False},
            'metadata_actions': [], 'data_plan': {},
            'warnings': [], 'errors': [f"Unexpected error: {e}"],
            'prompt': prompt,
        }


def to_legacy_config(metadata_actions: List[Dict]) -> Dict:
    """
    Convert prompt engine metadata_actions to the legacy config format
    expected by salesforce_config_utils.apply_configuration().
    """
    return {
        'type': 'configuration',
        'actions': metadata_actions,
        'analysis_method': 'prompt_engine_v2',
    }
