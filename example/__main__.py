"""
This example illustrates how Provider objects can be used to create resources under
different environmental configuration.
"""

import pulumi

# No provider given - uses default values from config (See Provider class for more info)

pulumi.export("ResourceOutput2", 123)
