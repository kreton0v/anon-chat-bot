from repository import repo
from utils import get_display_name


class CoinsService:
    REFERRAL_BATCH_SIZE = 5
    REFERRAL_REWARD = 100

    def add_coins(self, user_id: int, amount: int) -> int:
        p = repo.get_profile(user_id)
        p.coins += amount
        repo.save_profile(p)
        return p.coins

    def spend_coins(self, user_id: int, amount: int) -> bool:
        p = repo.get_profile(user_id)
        if p.coins < amount:
            return False
        p.coins -= amount
        repo.save_profile(p)
        return True

    def check_referral_reward(self, referrer_id: int) -> tuple:
        p = repo.get_profile(referrer_id)
        count = len(p.referrals)
        earned_batches = p.referral_batches
        new_batches = count // self.REFERRAL_BATCH_SIZE - earned_batches
        if new_batches > 0:
            reward = new_batches * self.REFERRAL_REWARD
            p.referral_batches = count // self.REFERRAL_BATCH_SIZE
            p.coins += reward
            repo.save_profile(p)
            return True, reward, count
        return False, 0, count

    def register_referral(self, user_id: int, referrer_id: int):
        p = repo.get_profile(user_id)
        if p.referred_by or user_id == referrer_id:
            return False
        p.referred_by = referrer_id
        repo.save_profile(p)
        return True

    def track_chat_duration(self, user_id: int, duration_seconds: int):
        if duration_seconds < 60:
            return
        p = repo.get_profile(user_id)
        referrer = p.referred_by
        if not referrer or referrer == user_id:
            return
        ref_p = repo.get_profile(referrer)
        if user_id not in ref_p.referrals:
            ref_p.referrals.append(user_id)
            repo.save_profile(ref_p)
            self.check_referral_reward(referrer)


coins = CoinsService()
