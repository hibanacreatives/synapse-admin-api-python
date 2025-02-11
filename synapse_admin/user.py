"""MIT License

Copyright (c) 2020 Knugi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""

import hashlib
import hmac
from synapse_admin.base import Admin, SynapseException, Utility, Contents
from typing import Union, Tuple


class User(Admin):
    """
    Wapper class for admin API for user management

    Reference:
        https://github.com/matrix-org/synapse/blob/master/docs/admin_api/user_admin_api.md
        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/account_validity.md
        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/room_membership.md
    """

    ORDER = ("name", "is_guest", "admin", "user_type", "deactivated",
             "shadow_banned", "displayname", "avatar_url", "creation_ts")

    def __init__(
        self,
        server_addr: str = None,
        server_addr_ext: str = None,
        server_port: int = 443,
        access_token: str = None,
        server_protocol: str = None,
        suppress_exception: bool = False
    ):
        super().__init__(
            server_addr=server_addr,
            server_addr_ext=server_addr_ext,
            server_port=server_port,
            access_token=access_token,
            server_protocol=server_protocol,
            suppress_exception=suppress_exception
        )
        self.devices = _Device(
            self.server_addr,
            self.connection,
            suppress_exception
        )
        self.registration_tokens = _RegistrationTokens(
            self.server_addr,
            self.connection,
            suppress_exception
        )
        self._create_alias()

    def _create_alias(self) -> None:
        """Create alias for some methods"""
        self.creates = self.create = self.create_modify  # For compatibility
        self.modify = self.create_modify
        self.details = self.query

    def lists(
        self,
        offset: int = 0,
        limit: int = 100,
        userid: str = None,
        name: str = None,
        guests: bool = True,
        deactivated: bool = False,
        order_by: str = None,
        _dir: str = "f"
    ) -> Contents:
        """List all local users

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#list-accounts

        Args:
            offset (int, optional): equivalent to "from". Defaults to 0. # noqa: E501
            limit (int, optional): equivalent to "limit". Defaults to 100.
            userid (str, optional): equivalent to "user_id". Defaults to None.
            name (str, optional): equivalent to "name". Defaults to None.
            guests (bool, optional): equivalent to "guests". Defaults to True.
            deactivated (bool, optional): equivalent to "deactivated". Defaults to False. # noqa: E501
            order_by (str, optional): equivalent to "order_by". Defaults to None.
            _dir (str, optional): equivalent to "dir". Defaults to "f".

        Returns:
            Contents: list of user
        """
        optional_str = ""
        if userid is not None:
            userid = self.validate_username(userid)
            optional_str += f"&user_id={userid}"
        if name is not None:
            optional_str += f"&name={name}"
        if order_by is not None:
            if order_by not in User.ORDER:
                raise ValueError(
                    "Argument 'order_by' must be included in User.ORDER, "
                    "for details please read the documentation."
                )
            optional_str += f"&order_by={order_by}"

        resp = self.connection.request(
            "GET",
            self.admin_patterns(
                f"/users?from={offset}&limit={limit}&guests="
                f"{Utility.get_bool(guests)}&deactivated="
                f"{Utility.get_bool(deactivated)}&dir={_dir}{optional_str}",
                2
            )
        )
        data = resp.json()
        if resp.status_code == 200:
            return Contents(
                data["users"],
                data["total"],
                data.get("next_token", None)
            )
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def create_modify(
        self,
        userid: str,
        *,
        password: str = None,
        displayname: str = None,
        threepids: list = None,
        avatar_url: str = None,
        admin: bool = None,
        deactivated: bool = None,
        external_ids: list = None,
        user_type: Union[str, None] = "",
        logout: bool = None
    ) -> bool:
        """Create or modify a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#create-or-modify-account

        Args:
            userid (str): The user id of the user
            password (str, optional): equivalent to "password". Defaults to None. # noqa: E501
            displayname (str, optional): equivalent to "displayname". Defaults to None.
            threepids (list, optional): equivalent to "threepids". Defaults to None.
            avatar_url (str, optional): equivalent to "avatar_url". Defaults to None.
            admin (bool, optional): equivalent to "admin". Defaults to None.
            deactivated (bool, optional): equivalent to "deactivated". Defaults to None.
            external_ids (list, optional): equivalent to "external_ids". Defaults to None.
            user_type (Union[str, None], optional): equivalent to "user_type", empty str to leave this value unchange. Defaults to "".

        Returns:
            bool: The creation of user is successful or not
        """
        body = {}
        if password:
            body["password"] = password
        if displayname:
            body["displayname"] = displayname
        if threepids:
            body["threepids"] = threepids
        if avatar_url:
            body["avatar_url"] = avatar_url
        if isinstance(admin, bool):
            body["admin"] = admin
        if isinstance(deactivated, bool):
            body["deactivated"] = deactivated
        if external_ids:
            body["external_ids"] = external_ids
        if user_type != "":
            body["user_type"] = user_type
        if isinstance(logout, bool):
            body["logout_devices"] = logout

        userid = self.validate_username(userid)
        resp = self.connection.request(
            "PUT",
            self.admin_patterns(f"/users/{userid}", 2),
            json=body
        )
        if resp.status_code == 200 or resp.status_code == 201:
            return True
        else:
            data = resp.json()
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def query(self, userid: str) -> dict:
        """Query a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#query-user-account

        Args:
            userid (str): the user you want to query

        Returns:
            dict: account information
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/users/{userid}", 2)
        )
        data = resp.json()
        if resp.status_code == 200 or resp.status_code == 201:
            return data
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def active_sessions(self, userid: str) -> list:
        """Query a user for their current sessions

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#query-current-sessions-for-a-user

        Args:
            userid (str): the user you want to query

        Returns:
            list: list of sessions
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/whois/{userid}", 1)
        )
        data = resp.json()["devices"][""]
        return data["sessions"][0]["connections"]

    def deactivate(self, userid: str, erase: bool = True) -> bool:
        """Deactivate a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#deactivate-account

        Args:
            userid (str): the account you want to deactivate
            erase (bool, optional): whether to erase all information related to the user. Defaults to True. # noqa: E501

        Returns:
            bool: success or not
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "POST",
            self.admin_patterns(f"/deactivate/{userid}", 1),
            json={"erase": erase}
        )
        data = resp.json()
        if resp.status_code == 200:
            return data["id_server_unbind_result"] == "success"
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def reactivate(self, userid: str, password: str = None) -> bool:
        """Reactivate a deactivated account

        Args:
            userid (str): the account you want to reactivate
            password (str, optional): a new password for the account. Defaults to None. # noqa: E501

        Returns:
            bool: success or not
        """
        if password is None:
            password = Utility.get_password()
        if not isinstance(password, str):
            raise TypeError(
                "Argument 'password' should be a "
                f"string but not {type(password)}"
            )
        return self.modify(userid, password=password, deactivated=False)

    def reset_password(
        self,
        userid: str,
        password: str = None,
        logout: bool = True
    ) -> bool:
        """Reset a user password

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#reset-password

        Args:
            userid (str): the account you want to reset their password
            password (str, optional): the new password. Defaults to None.
            logout (bool, optional): whether or not to logout all current devices. Defaults to True. # noqa: E501

        Returns:
            bool: success or not
        """
        userid = self.validate_username(userid)
        if password is None:
            password = Utility.get_password()
        resp = self.connection.request(
            "POST",
            self.admin_patterns(f"/reset_password/{userid}", 1),
            json={"new_password": password, "logout_devices": logout}
        )
        if resp.status_code == 200:
            return True
        else:
            data = resp.json()
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def is_admin(self, userid: str) -> bool:
        """To see if a user is a server admin

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#get-whether-a-user-is-a-server-administrator-or-not

        Args:
            userid (str): the user you want to query

        Returns:
            bool: is or is not an admin
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/users/{userid}/admin", 1)
        )
        return resp.json()["admin"]

    def set_admin(
        self,
        userid: str,
        activate: bool = None
    ) -> Tuple[bool, bool]:
        """Set or revoke server admin role for a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#change-whether-a-user-is-a-server-administrator-or-not

        Args:
            userid (str): the user you want to set or revoke
            activate (bool, optional): True to set as admin, False to revoke their admin, leave None to let the program decide. Defaults to None. # noqa: E501

        Returns:
            Tuple[bool, bool]: success or not, is the user admin or not now
        """
        if activate is None:
            activate = not self.is_admin(userid)
        elif not isinstance(activate, bool):
            raise TypeError(
                "Argument 'activate' only accept "
                f"boolean but not {type(activate)}."
            )
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "PUT",
            self.admin_patterns(f"/users/{userid}/admin", 1),
            json={"admin": activate}
        )
        if resp.status_code == 200:
            # TBD: whether or not to return both action status and admin status
            return True, activate
        else:
            data = resp.json()
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def joined_room(self, userid: str) -> Contents:
        """Query the room a user joined

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#list-room-memberships-of-a-user

        Args:
            userid (str): the user you want to query

        Returns:
            Contents: list of joined_room
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/users/{userid}/joined_rooms", 1)
        )
        data = resp.json()
        if resp.status_code == 200:
            return Contents(data["joined_rooms"], data["total"])
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def join_room(self, userid: str, roomid: str) -> bool:
        """Force an user to join a room

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/room_membership.md#edit-room-membership-api

        Args:
            userid (str): the user you want to add to the room
            roomid (str): the room you want to add the user into

        Returns:
            bool: success or not
        """
        userid = self.validate_username(userid)
        roomid = self.validate_room(roomid)
        resp = self.connection.request(
            "POST",
            self.admin_patterns(f"/join/{roomid}", 1),
            json={"user_id": userid}
        )
        data = resp.json()
        if resp.status_code == 200:
            if "room_id" in data and data["room_id"] == roomid:
                return True
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def validity(
        self,
        userid: str,
        expiration: int = 0,
        enable_renewal_emails: bool = True
    ) -> int:
        """Set an account validity

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/account_validity.md#account-validity-api

        Args:
            userid (str): the user you want to set
            expiration (int, optional): target expiration timestamp in millisecond. Defaults to 0. # noqa: E501
            enable_renewal_emails (bool, optional): enable or disable the renewal email. Defaults to True. # noqa: E501

        Returns:
            int: the new expiration timestamp in millisecond
        """
        if expiration is not None and not isinstance(expiration, int):
            raise TypeError(
                "Argument 'expiration' only accept "
                f"int but not {type(expiration)}."
            )

        userid = self.validate_username(userid)
        data = {
            "user_id": userid,
            "enable_renewal_emails": enable_renewal_emails,
            "expiration_ts": expiration
        }

        resp = self.connection.request(
            "POST",
            self.admin_patterns("/account_validity/validity", 1),
            json=data
        )
        data = resp.json()
        if resp.status_code == 200:
            return data["expiration_ts"]
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def register(
        self,
        username: str,
        shared_secret: Union[str, bytes],
        *,
        displayname: str,
        password: str = None,
        admin: bool = False
    ) -> dict:
        """Register a new user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/register_api.md#shared-secret-registration

        Args:
            username (str): the username
            shared_secret (Union[str, bytes]): the shared secret defined in homeserver.yaml # noqa: E501
            displayname (str): the display name for the user
            password (str, optional): the password for the user. Defaults to None.
            admin (bool, optional): whether or not to set the user as server admin. Defaults to False. # noqa: E501

        Returns:
            dict: a dict including access token and other information of the new account
        """
        nonce = self._get_register_nonce()
        if password is None:
            password = Utility.get_password()
        data = {
            "nonce": nonce,
            "username": username,
            "displayname": displayname,
            "password": password,
            "admin": admin,
            "mac": self._generate_mac(nonce, username, password, shared_secret)
        }
        resp = self.connection.request(
            "POST",
            self.admin_patterns("/register", 1),
            json=data
        )

        data = resp.json()
        if resp.status_code == 200:
            return data
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def _get_register_nonce(self) -> str:
        """Get a register nonce

        Returns:
            str: register nonce
        """
        resp = self.connection.request(
            "GET",
            self.admin_patterns("/register", 1)
        )
        return resp.json()["nonce"]

    def _generate_mac(
        self,
        nonce: Union[str, bytes],
        user: Union[str, bytes],
        password: Union[str, bytes],
        shared_secret: Union[str, bytes],
        admin: bool = False,
        user_type: Union[str, bytes] = None
    ) -> str:
        """Generate a HMAC for register

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/register_api.md#shared-secret-registration

        Args:
            nonce (Union[str, bytes]): nonce for registation, can be obtained from the homeserver
            user (Union[str, bytes]): the username
            password (Union[str, bytes]): the password
            shared_secret (Union[str, bytes]): shared secret for registation, can be obtained from homeserver.yaml  # noqa: E501
            admin (bool, optional): whether the user is admin or not. Defaults to False.
            user_type (Union[str, bytes], optional): the type of the user. Defaults to None.

        Returns:
            str: HMAC-SHA1 digest in hex
        """
        if isinstance(nonce, str):
            nonce = nonce.encode()
        elif not isinstance(nonce, bytes):
            raise TypeError("Argument nonce must be str or bytes")
        if isinstance(user, str):
            user = user.encode()
        elif not isinstance(user, bytes):
            raise TypeError("Argument user must be str or bytes")
        if isinstance(password, str):
            password = password.encode()
        elif not isinstance(password, bytes):
            raise TypeError("Argument password must be str or bytes")
        if isinstance(shared_secret, str):
            shared_secret = shared_secret.encode()
        elif not isinstance(shared_secret, bytes):
            raise TypeError("Argument shared_secret must be str or bytes")
        if user_type is not None:
            if isinstance(user_type, str):
                user_type = user_type.encode()
            elif not isinstance(user_type, bytes):
                raise TypeError(
                    "Argument user_type must be"
                    "str or bytes or None"
                )

        if admin:
            admin = b"admin"
        else:
            admin = b"notadmin"

        msg = b"%s\x00%s\x00%s\x00%s" % (nonce, user, password, admin)
        if user_type:
            msg += b"\x00%s" % (user_type,)

        digest = hmac.new(
            shared_secret,
            msg,
            digestmod=hashlib.sha1,
        ).hexdigest()

        return digest

    def list_media(
        self,
        userid: str,
        limit: int = 100,
        _from: int = 0,
        order_by: int = None,
        _dir: str = "f"
    ) -> Contents:
        """list all media sent by the user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#list-media-of-a-user

        Args:
            userid (str): the user you want to query
            limit (int, optional): equivalent to "limit". Defaults to 100.
            _from (int, optional): equivalent to "from". Defaults to 0.
            order_by (int, optional): equivalent to "order_by". Defaults to None. # noqa: E501
            _dir (str, optional): equivalent to "dir". Defaults to "f".

        Returns:
            Contents: list of media # noqa: E501
        """
        userid = self.validate_username(userid)
        optional_str = ""
        if order_by is not None:
            optional_str += f"&order_by={order_by}"
        resp = self.connection.request(
            "GET",
            self.admin_patterns(
                f"/users/{userid}/media?"
                f"limit={limit}&from={_from}"
                f"&dir={_dir}{optional_str}", 1)
        )
        data = resp.json()
        if resp.status_code == 200:
            if "next_token" not in data:
                next_token = 0
            else:
                next_token = data["next_token"]
            return Contents(data["media"], data["total"], next_token)
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def login(self, userid: str, valid_until_ms: int = None) -> str:
        """Login as a user and get their access token

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#login-as-a-user

        Args:
            userid (str): the user you want to login
            valid_until_ms (int, optional): the validity period in millisecond. Defaults to None. # noqa: E501

        Returns:
            str: access token of the user
        """
        if isinstance(valid_until_ms, int):
            data = {"valid_until_ms": valid_until_ms}
        elif valid_until_ms is None:
            data = {}
        else:
            raise TypeError(
                "Argument valid_until_ms must be int "
                f"but not {type(valid_until_ms)}."
            )

        userid = self.validate_username(userid)
        resp = self.connection.request(
            "POST",
            self.admin_patterns(f"/users/{userid}/login", 1),
            json=data
        )
        data = resp.json()
        if resp.status_code == 200:
            return data["access_token"]
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def get_ratelimit(self, userid: str) -> Tuple[int, int]:
        """Query the ratelimit applied to a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#get-status-of-ratelimit

        Args:
            userid (str): the user you want to query

        Returns:
            Tuple[int, int]: the current messages per second and burst count
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "GET",
            self.admin_patterns(
                f"/users/{userid}/"
                "override_ratelimit",
                1
            )
        )
        data = resp.json()
        if data == {}:
            return data
        if resp.status_code == 200:
            return data["messages_per_second"], data["burst_count"]
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def set_ratelimit(self, userid: str, mps: int, bc: int) -> Tuple[int, int]:
        """Set the ratelimit applied to a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#set-ratelimit

        Args:
            userid (str): the user you want to set
            mps (int): messages per second
            bc (int): burst count

        Returns:
            Tuple[int, int]: the current messages per second and burst count
        """
        userid = self.validate_username(userid)
        data = {"messages_per_second": mps, "burst_count": bc}
        resp = self.connection.request(
            "POST",
            self.admin_patterns(
                f"/users/{userid}/"
                "override_ratelimit",
                1
            ),
            json=data
        )
        data = resp.json()
        if resp.status_code == 200:
            return data["messages_per_second"], data["burst_count"]
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def disable_ratelimit(self, userid: str) -> Tuple[int, int]:
        """Disable the ratelimit applied to a user

        Args:
            userid (str): the user you want to disable their ratelimit

        Returns:
            Tuple[int, int]: the current messages per second and burst count
        """
        return self.set_ratelimit(userid, 0, 0)

    def delete_ratelimit(self, userid: str) -> bool:
        """Delete the ratelimit applied to a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#delete-ratelimit

        Args:
            userid (str): the user you want to delete their ratelimit

        Returns:
            bool: success or not
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "DELETE",
            self.admin_patterns(
                f"/users/{userid}/"
                "override_ratelimit",
                1
            )
        )
        data = resp.json()
        if data == {}:
            return True
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def pushers(self, userid: str) -> Contents:
        """list pushers of a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#list-all-pushers

        Args:
            userid (str): the user you want to query

        Returns:
            Contents: list of pushers
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/users/{userid}/pushers", 1)
        )
        data = resp.json()
        if resp.status_code == 200:
            return Contents(data["pushers"], data["total"])
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def shadow_ban(self, userid: str) -> bool:
        """Shadow ban a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#controlling-whether-a-user-is-shadow-banned

        Args:
            userid (str): the user you want to shadow ban

        Returns:
            bool: success or not
        """
        print("WARNING! This action may Undermine the TRUST of YOUR USERS.")
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "POST",
            self.admin_patterns(f"/users/{userid}/shadow_ban", 1)
        )
        data = resp.json()
        if len(data) == 0:
            return True
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def username_available(self, userid: str) -> bool:
        """Check if provided username is available or not

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#check-username-availability

        Args:
            userid (str): the username you want to check

        Returns:
            bool:
                True: the username is available
                False: the username is used

        Please note that this method DOES NOT supress exception
        """
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/username_available?username={userid}", 1)
        )
        data = resp.json()
        if "available" in data:
            return data["available"]
        elif "errcode" in data and data["errcode"] == "M_USER_IN_USE":
            return False
        else:
            raise SynapseException(data["errcode"], data["error"])

    def unshadow_ban(self, userid: str) -> bool:
        """Un-shadow ban a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#controlling-whether-a-user-is-shadow-banned

        Args:
            userid (str): the user you want to un-shadow ban

        Returns:
            bool: success or not
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "DELETE",
            self.admin_patterns(f"/users/{userid}/shadow_ban", 1)
        )
        data = resp.json()
        if len(data) == 0:
            return True
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])
    
    def data(self, userid: str) -> dict:
        """Query the specified user account's data

        Args:
            userid (str): the user to be queried

        Returns:
            dict: a dict containing the account data
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/users/{userid}/accountdata", 1)
        )
        data = resp.json()
        if resp.status_code == 200:
            return data["account_data"]
        else:
            if self.suppress_exception:
                return False, data["errcode"], data["error"]
            else:
                raise SynapseException(data["errcode"], data["error"])


class _Device(Admin):
    def __init__(self, server_addr, conn, suppress_exception):
        self.server_addr = server_addr
        self.connection = conn
        self.suppress_exception = suppress_exception

    def lists(self, userid: str) -> list:
        """List all active devices of a user

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#list-all-devices

        Args:
            userid (str): the user you want to query

        Returns:
            list: list of active devices
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/users/{userid}/devices", 2)
        )
        data = resp.json()
        if resp.status_code == 200:
            return data["devices"]
        else:
            if self.suppress_exception:
                return False, data["errcode"], data["error"]
            else:
                raise SynapseException(data["errcode"], data["error"])

    def delete(self, userid: str, device: Union[str, list]) -> bool:
        """Delete active device(s)

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#delete-multiple-devices

        Args:
            userid (str): the owner of the device(s)
            device (Union[str, list]): the device(s) you want to delete

        Returns:
            bool: success or not
        """
        if isinstance(device, list) and len(device) > 1:
            return self._delete_multiple(userid, device)
        elif isinstance(device, list) and len(device) == 1:
            device = device[0]

        userid = self.validate_username(userid)
        resp = self.connection.request(
            "DELETE",
            self.admin_patterns(f"/users/{userid}/devices/{device}", 2)
        )
        if resp.status_code == 200:
            return True
        else:
            data = resp.json()
            if self.suppress_exception:
                return False, data["errcode"], data["error"]
            else:
                raise SynapseException(data["errcode"], data["error"])

    def _delete_multiple(self, userid: str, devices: list) -> bool:
        """Delete multiple active devices (You should use User.delete)

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#delete-multiple-devices

        Args:
            userid (str): the owner of the device(s)
            device (list): the device(s) you want to delete

        Returns:
            bool: success or not
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "POST",
            self.admin_patterns(f"/users/{userid}/delete_devices", 2),
            json={"devices": devices}
        )
        if resp.status_code == 200:
            return True
        else:
            data = resp.json()
            if self.suppress_exception:
                return False, data["errcode"], data["error"]
            else:
                raise SynapseException(data["errcode"], data["error"])

    def show(self, userid: str, device: str) -> dict:
        """Show details of a device

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#show-a-device

        Args:
            userid (str): the owner of the device
            device (str): the device you want to query

        Returns:
            dict: dict including last seen IP address and other information
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/users/{userid}/devices/{device}", 2)
        )
        data = resp.json()
        if resp.status_code == 200:
            return data
        else:
            if self.suppress_exception:
                return False, data["errcode"], data["error"]
            else:
                raise SynapseException(data["errcode"], data["error"])

    def update(self, userid: str, device: str, display_name: str) -> bool:
        """Update the display name of a device

        https://github.com/matrix-org/synapse/blob/develop/docs/admin_api/user_admin_api.md#update-a-device

        Args:
            userid (str): the owner of the device
            device (str): the device you want to modify
            display_name (str): the new display name

        Returns:
            bool: success or not
        """
        userid = self.validate_username(userid)
        resp = self.connection.request(
            "PUT",
            self.admin_patterns(f"/users/{userid}/devices/{device}", 2),
            json={"display_name": display_name}
        )
        if resp.status_code == 200:
            return True
        else:
            data = resp.json()
            if self.suppress_exception:
                return False, data["errcode"], data["error"]
            else:
                raise SynapseException(data["errcode"], data["error"])


class _RegistrationTokens(Admin):
    def __init__(self, server_addr, conn, suppress_exception):
        self.server_addr = server_addr
        self.connection = conn
        self.suppress_exception = suppress_exception

    def lists(self, valid: bool = None) -> list:
        """List all registration tokens

        https://github.com/matrix-org/synapse/blob/develop/docs/usage/administration/admin_api/registration_tokens.md#list-all-tokens

        Args:
            valid (bool, optional): filter returned tokens based on their validity. Defaults to None (return all tokens).  # noqa: E501

        Returns:
            list: a list of registration tokens and their details
        """
        resp = self.connection.request(
            "GET",
            self.admin_patterns("/registration_tokens", 1),
            params={"valid": valid} if isinstance(valid, bool) else {}
        )
        data = resp.json()
        if resp.status_code == 200:
            return data["registration_tokens"]
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def query(self, token: str) -> dict:
        """Get the details of a registration token

        https://github.com/matrix-org/synapse/blob/develop/docs/usage/administration/admin_api/registration_tokens.md#get-one-token

        Args:
            token (str): the token to query

        Returns:
            dict: details of the token
        """
        resp = self.connection.request(
            "GET",
            self.admin_patterns(f"/registration_tokens/{token}", 1),
        )
        data = resp.json()
        if resp.status_code == 200:
            return data
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def create(
        self,
        token: str = None,
        uses_allowed: int = None,
        expiry_time: int = None,
        length: int = None
    ) -> dict:
        """Create a registration token

        https://github.com/matrix-org/synapse/blob/develop/docs/usage/administration/admin_api/registration_tokens.md#create-token

        Args:
            token (str, optional): equivalent to "token". Defaults to None (randomly generated).  # noqa: E501
            uses_allowed (int, optional): equivalent to "uses_allowed". Defaults to None.
            expiry_time (int, optional): equivalent to "expiry_time". Defaults to None.
            length (int, optional): equivalent to "length". Defaults to None.

        Returns:
            dict: details of created token
        """
        body = {}
        if token:
            body["token"] = token
        if uses_allowed:
            body["uses_allowed"] = uses_allowed
        if expiry_time:
            body["expiry_time"] = expiry_time
        if length:
            body["length"] = length

        resp = self.connection.request(
            "POST",
            self.admin_patterns("registration_tokens/new", 1),
            json=body
        )
        data = resp.json()
        if resp.status_code == 200:
            return data
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def update(
        self,
        token: str,
        uses_allowed: int = None,
        expiry_time: int = None
    ) -> dict:
        """Update a registration token

        https://github.com/matrix-org/synapse/blob/develop/docs/usage/administration/admin_api/registration_tokens.md#update-token

        Args:
            token (str): equivalent to "token".
            uses_allowed (int, optional): equivalent to "uses_allowed". Defaults to None.  # noqa: E501
            expiry_time (int, optional): equivalent to "expiry_time". Defaults to None.  # noqa: E501

        Returns:
            dict: new details of the token
        """
        body = {}
        if uses_allowed:
            body["uses_allowed"] = uses_allowed
        if expiry_time:
            body["expiry_time"] = expiry_time

        resp = self.connection.request(
            "PUT",
            self.admin_patterns(f"registration_tokens/{token}", 1),
            json=body
        )
        data = resp.json()
        if resp.status_code == 200:
            return data
        else:
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])

    def delete(
        self,
        token: str
    ) -> bool:
        """Delete a registration token

        https://github.com/matrix-org/synapse/blob/develop/docs/usage/administration/admin_api/registration_tokens.md#delete-token

        Args:
            token (str): the token needed to be deleted

        Returns:
            bool: whether the deletion is successful or not
        """
        resp = self.connection.request(
            "DELETE",
            self.admin_patterns(f"registration_tokens/{token}", 1),
        )
        if resp.status_code == 200:
            return True
        else:
            data = resp.json()
            if self.suppress_exception:
                return False, data
            else:
                raise SynapseException(data["errcode"], data["error"])
