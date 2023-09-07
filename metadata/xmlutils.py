"""
Common functions and classes defined here

@author: Enoc Martínez
@contact: enoc.martinez@upc.edu
"""

import sys
import xml.etree as etree

# Namespaces used by SensorML, SOS and O&M Ddocuments


ns = {'swe':'http://www.opengis.net/swe/2.0',
      'sos': 'http://www.opengis.net/sos/2.0',
      'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
      'ns': 'http://www.opengis.net/swe/2.0',
      'xlink': 'http://www.w3.org/1999/xlink',
      'swes': 'http://www.opengis.net/swes/2.0',
      'gml': 'http://www.opengis.net/gml/3.2',
      'sml': 'http://www.opengis.net/sensorml/2.0',
      'om': 'http://www.opengis.net/om/2.0',
      'sams': 'http://www.opengis.net/samplingSpatial/2.0',
      'sf': 'http://www.opengis.net/sampling/2.0',
      'ows': 'http://www.opengis.net/ows/1.1',
      'drt': 'http://www.opengis.net/drt/1.0',
      'gda': 'http://www.opengis.net/sosgda/1.0',
      "gmd": "http://www.isotc211.org/2005/gmd",
      "gco": "http://www.isotc211.org/2005/gco"}

__enable_debug__ = False


def dbg(*arguments):
    state = False
    if __enable_debug__:
        s = str(*arguments)
        for char in s:
            if state == False and char == '\"':
                state = True
            elif state == True and char == '\"':
                state = False
            else:
                sys.stdout.write(char)
        sys.stdout.write('\n')


def has_namespace(tag):
    """This function checks if a tag has a namespace"""
    if ':' in tag:
        return True
    else:
        return False


def true_false_string(x):
    """Converts from boolean type to 'true' or 'false' string"""
    if type(x) != type(True):
        raise ValueError("Input not boolean")

    elif x == True:
        return 'true'
    else:
        return 'false'


class GenericXML:
    """
    Implements Generic functions for XML manipulation
    """

    def __init__(self):
        self.xml = ""
        pass

    def generate_document(self, outfile="", header=False):
        """
        Generates an XML document based on self.tree structure. If outfile is set the document is
        stored in a file.
        :param outfile: if set stores the XML document in file
        :return: xml document as string
        """
        self.xml = etree.tostring(self.tree, encoding="UTF-8", pretty_print=True, xml_declaration=True)
        s = self.xml.decode()
        if outfile:
            with open(outfile, 'w') as f:
                if header:
                    pass
                f.write(s)
        return self.xml


def set_child_label(root, newvalue):
    """Modifies the content of the children's label element"""
    return generic_set_child_element(root, newvalue, 'label')


def set_child_definition(root, newvalue):
    """Modifies the content of the children's definition element"""
    return generic_set_child_element(root, 'definition', newvalue)


def set_child_value(root, newvalue):
    """Modifies the content of the children's value element"""
    return generic_set_child_element(root, newvalue, 'value')


def set_value_to_child(root, newvalue, tag, attr=None, attr_value=None):
    """Looks for the an element, then looks for its ns:value child and sets the text value"""
    element = get_element(root, tag, attr=attr, attr_value=attr_value)
    set_child_value(element, newvalue)


def set_label_to_child(root, newvalue, tag, attr=None, attr_value=None):
    """Looks for the an element, then looks for its ns:value child and sets the text value"""
    element = get_element(root, tag, attr=attr, attr_value=attr_value)
    set_child_label(element, newvalue)


def generic_set_child_element(root, newvalue, childtag, attr=None, attr_value=None):
    """Generic method that modifies the value of a child element"""
    child = None
    if has_namespace(childtag) == True:
        child = get_element(newvalue, childtag, attr=attr, attr_value=attr_value)

    # Loop through all the namespaces if namespace not provided
    else:
        for currents in list(ns.keys()):
            tag_with_ns = currents + ':' + childtag
            try:
                child = get_element(root, tag_with_ns, attr, attr_value)
            except LookupError:
                pass
            if child != None:
                break
    if child == None:
        raise LookupError("Child element \"%s\" not found" % childtag)

    child.text = newvalue


def set_child_attribute(root, childtag, attr, attr_value, namespace=None):
    child = None
    if 'namespace' != None:
        xpath = './' + namespace + ':' + childtag
        child = root.find(xpath, namespace=ns)

    # Loop through all the namespaces if namespace not provided
    else:
        for currentns in list(ns.keys()):
            xpath = './' + currentns + ':' + childtag
            child = root.find(xpath, namespace=ns)
            if child != None:
                break

    if child == None:
        raise ValueError("Child element %s not found", childtag)

    print("Setting attr", attr, "to", attr_value)
    # Modify the dictionary containing the child's attributes
    if attr in child.attrib:
        child.attrib[attr] = attr_value
        # if element does not exist append a new element to the dictionary
    else:
        new_attribute = {attr: attr_value}
        child.attrib.update(new_attribute)  # Update the attribute dictionary


def set_value(root, value, tag, attr=None, attr_value=None):
    """Looks for an elements and sets it's value"""
    element = get_element(root, tag, attr=attr, attr_value=attr_value)
    element.text = value
    return element


def set_attribute(root, value, tag, attr):
    """Looks for an elements and sets it's value"""
    element = get_element(root, tag, attr=attr)
    element.attrib[attr] = value
    return element


def remove_element(root, tag, attr=None, attr_value=None):
    """
    looks for an element and removes it from the tree
    :param root: etree root to look
    :param tag: element tag (including namespace)
    :param attr: attribute name
    :param attr_value: attribute value
    """
    element = get_element(root, tag, attr=attr, attr_value=attr_value)
    element.getparent().remove(element)


def get_elements(root, tag, attr=None, attr_value=None):
    """
    Looks in root for all elements with matching tag, attribute name and attribute value
    :param root: etree root to look
    :param tag: element tag (including namespace)
    :param attr: attribute name
    :param attr_value: attribute value
    :returns: list of matching elements
    """
    dbg('looking for tag \"%s\" attr \"%s\" attr_value \"%s\"' % (tag, attr, attr_value))
    # If no attributes only one candidates should be found by tag, otherwise error
    if tag != None and attr == None:
        xpath = './/' + tag
        return root.findall(xpath, namespaces=ns)

    # Element with attribute, get all subelements that match the tag with the attribute
    xpath = './/' + tag + '[@%s]' % attr
    candidates = root.findall(xpath, namespaces=ns)
    dbg('got %d elements  with tag \"%s\"' % (len(candidates), tag))

    selected = []
    for candidate in candidates:
        if attr in candidate.attrib.keys():
            selected.append(candidate)

    dbg('got %d elements  with attr \"%s\"' % (len(selected), attr))

    # If attribute without value
    if attr_value == None:
        return selected

    candidates = selected

    # If tag, attribute and value multiple values can be found, loop until matching
    # attribute value is found
    selected = []
    for element in candidates:
        if element.attrib.get(attr) == attr_value:
            selected.append(element)

    if len(selected) > 0:
        dbg('got %d elements  with value \"%s\"' % (len(selected), attr_value))
        return selected

    raise LookupError("Element not found %s %s=%s" % (tag, attr, attr_value))


def get_element(root, tag, attr=None, attr_value=None):
    """
    Looks in root for an elements with matching tag, attribute name and attribute value.
    If more than one element is found, error is raised
    :param root: etree root to look
    :param tag: element tag (including namespace)
    :param attr: attribute name
    :param attr_value: attribute value
    :returns: list of matching elements
    """
    candidates = get_elements(root, tag, attr=attr, attr_value=attr_value)

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        raise LookupError("Too many elements %s found, expected 1 got %d" % (tag, len(candidates)))

    raise LookupError("Element not found %s %s=%s" % (tag, attr, attr_value))


def get_children_index(root, tag):
    """
    This function looks at the children of root and returns the index of the children with matching tag
    :param root: etree element where to look for children
    :param tag: children tag
    :return: children index with matching tag
    :raises: LookupError if no matching children is found
    """
    if ":" in tag:
        # replace tag with namespace
        ns_tag = tag.split(':')[0]
        tag = "{%s}" % ns[ns_tag] + tag.split(":")[1]

    i = 0
    mylist = list(root)
    for i in range(0, len(mylist)):
        child = root[i]
        if child.tag == tag:
            return i
    raise LookupError("Children with tag %s not found in element %s " % (tag, root.tag))


def append_after(root, tag, element, comment=""):
    """
    This function appends "element" to the children list in root just after the children with matching tag
    :param root: etree element where to append
    :param tag: children tag after which the element will be appended
    :param element: etree Element to append
    :param comment: if comment is set, a comment with this text will be added before the element
    :raises: LookupError if no matching children is found
    """
    i = get_children_index(root, tag)
    if len(comment) > 0:
        comment_object = etree.Comment(comment)
        root.insert(i+1, comment_object)
        i += 1

    root.insert(i+1, element)


def append_before(root, tag, element, comment=""):
    """
    This function appends "element" to the children list in root just before the children with matching tag
    :param root: etree element where to append
    :param tag: children tag after which the element will be appended
    :param element: etree Element to append
    :param comment: if comment is set, a comment with this text will be added before the element
    :raises: LookupError if no matching children is found
    """
    i = get_children_index(root, tag)

    if len(comment) > 0:
        comment_object = etree.Comment(comment)
        root.insert(i, comment_object)
        i += 1

    root.insert(i, element)



