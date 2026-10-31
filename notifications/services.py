class MockNotificationProvider:
    def send(self, phone, message):
        return {"provider": "mock", "status": "mock_sent", "phone": phone, "message": message}


class SolapiNotificationProvider:
    def send(self, phone, message):
        raise NotImplementedError("SolAPI 연동은 MVP에서 구현하지 않았습니다. 실제 발송은 수행되지 않습니다.")


class NotificationService:
    def __init__(self, provider=None):
        self.provider = provider or MockNotificationProvider()

    def send(self, phone, message):
        if not isinstance(self.provider, MockNotificationProvider):
            raise RuntimeError("실전 문자 발송은 명시적으로 구현·검토되기 전까지 사용할 수 없습니다.")
        return self.provider.send(phone, message)
