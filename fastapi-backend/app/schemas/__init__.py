"""Pydantic request/response models, one module per router.

"Schema" here means the *shape of the JSON on the wire* — not the database
schema. The ORM models in ``app/models`` describe tables; these describe
what a client sends and what it gets back. Keeping them separate is what
lets us, for example, accept a ``password`` on register and never return a
``password_hash`` on any response.
"""
