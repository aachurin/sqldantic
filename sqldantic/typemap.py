import ipaddress

from .sqltypes import InetType

DEFAULT_TYPE_MAP = {
    ipaddress.IPv4Address: InetType(ipaddress.IPv4Address),
    ipaddress.IPv6Address: InetType(ipaddress.IPv6Address),
}

# if issubclass(type_, float):
#     return Float
# if issubclass(type_, bool):
#     return Boolean
# if issubclass(type_, int):
#     return Integer
# if issubclass(type_, datetime):
#     return DateTime
# if issubclass(type_, date):
#     return Date
# if issubclass(type_, timedelta):
#     return Interval
# if issubclass(type_, time):
#     return Time
# if issubclass(type_, bytes):
#     return LargeBinary
# if issubclass(type_, Decimal):
#     return Numeric(
#         precision=getattr(metadata, "max_digits", None),
#         scale=getattr(metadata, "decimal_places", None),
#     )
# if issubclass(type_, ipaddress.IPv4Address):
#     return AutoString
# if issubclass(type_, ipaddress.IPv4Network):
#     return AutoString
# if issubclass(type_, ipaddress.IPv6Address):
#     return AutoString
# if issubclass(type_, ipaddress.IPv6Network):
#     return AutoString
# if issubclass(type_, Path):
#     return AutoString
# if issubclass(type_, uuid.UUID):
#     return GUID
