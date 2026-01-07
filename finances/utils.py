from django.core import signing

INVOICE_LINK_SALT = "invoice-public-link"


def generate_invoice_token(invoice_id):
    """
    Create a secure, signed token for public invoice access
    """
    return signing.dumps(
        {"invoice_id": invoice_id},
        salt=INVOICE_LINK_SALT
    )


def validate_invoice_token(token, max_age=60 * 60 * 24 * 7):
    """
    Validate token and return invoice_id
    Token expires in 7 days
    """
    return signing.loads(
        token,
        salt=INVOICE_LINK_SALT,
        max_age=max_age
    )
