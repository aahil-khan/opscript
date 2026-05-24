from serverkit.env.vars import EnvSnapshot


class EnvManager:
    def snapshot(self) -> EnvSnapshot:
        return EnvSnapshot()
