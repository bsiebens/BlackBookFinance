# @receiver(post_save, sender=Posting)
# def update_transaction_amounts(sender, instance, **kwargs) -> None:
#    instance.transaction.update_amounts()
from django.db.models.signals import post_save
from django.dispatch import receiver

from ledger.models import Posting


# noinspection PyUnusedLocal
@receiver(post_save, sender=Posting)
def update_balancing_amount(instance, **kwargs) -> None:
    """
    A signal handler to update the balance amount of a transaction whenever a posting is saved. This method ensures that the balance posting always has the correct calculated balance amount.

    :param instance: The specific instance of the sender that was saved.
    :type instance: Posting
    :return: None
    :rtype: None
    """

    try:
        balance_posting = instance.transaction.postings.get(is_balance_posting=True)
        balance_amount = instance.calculate_balance_amount()

        if balance_posting.amount != balance_amount:
            Posting.objects.filter(id=balance_posting.id).update(amount=balance_amount)

    except Posting.DoesNotExist:
        return
