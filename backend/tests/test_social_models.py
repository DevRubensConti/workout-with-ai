from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.auth.models import User, utcnow
from src.social.models import UserBlock, UserFollow, UserLocation, UserProfile


@pytest.fixture()
def db(session_factory):
    with session_factory() as session:
        yield session


def profile(db, username="ana"):
    user = User(name=username, email=f"{username}@example.com", password_hash="test")
    db.add(user)
    db.flush()
    item = UserProfile(user_id=user.id, username=username, display_name=username)
    db.add(item)
    db.commit()
    return item


def test_profile_is_optional_private_and_not_discoverable(db):
    user = User(name="Sem perfil", email="none@example.com", password_hash="test")
    db.add(user)
    db.commit()
    assert db.scalar(select(func.count()).select_from(UserProfile)) == 0
    item = profile(db)
    assert item.is_private is True
    assert item.nearby_enabled is False
    assert item.location is None


def test_only_one_profile_per_user(db):
    item = profile(db)
    db.add(UserProfile(user_id=item.user_id, username="outro", display_name="Outro"))
    with pytest.raises(IntegrityError):
        db.commit()


@pytest.mark.parametrize("username", ["Ana", "ab", "a" * 31, " ana", "ana "])
def test_username_constraints(db, username):
    with pytest.raises(IntegrityError):
        profile(db, username)


def test_username_is_unique(db):
    first = profile(db)
    other = profile(db, "bia")
    other.username = first.username
    with pytest.raises(IntegrityError):
        db.commit()


def test_follow_request_can_be_accepted_and_is_directional(db):
    ana, bia = profile(db), profile(db, "bia")
    request = UserFollow(follower_id=ana.user_id, following_id=bia.user_id)
    db.add(request)
    db.commit()
    assert request.status == "pending" and request.accepted_at is None
    request.status, request.accepted_at = "accepted", utcnow()
    db.add(UserFollow(follower_id=bia.user_id, following_id=ana.user_id))
    db.commit()
    assert db.scalar(select(func.count()).select_from(UserFollow)) == 2
    bia.is_private = False
    db.commit()
    assert db.get(UserProfile, bia.id).is_private is False


@pytest.mark.parametrize(
    "values",
    [
        {"status": "invalid"},
        {"status": "accepted"},
        {"status": "pending", "accepted_at": utcnow()},
    ],
)
def test_invalid_follow_state(db, values):
    ana, bia = profile(db), profile(db, "bia")
    db.add(UserFollow(follower_id=ana.user_id, following_id=bia.user_id, **values))
    with pytest.raises(IntegrityError):
        db.commit()


@pytest.mark.parametrize(
    "model,keys",
    [
        (UserFollow, ("follower_id", "following_id")),
        (UserBlock, ("blocker_id", "blocked_id")),
    ],
)
def test_self_connections_and_duplicates_are_rejected(db, model, keys):
    ana, bia = profile(db), profile(db, "bia")
    db.add(model(**dict(zip(keys, (ana.user_id, ana.user_id)))))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    values = dict(zip(keys, (ana.user_id, bia.user_id)))
    db.add(model(**values))
    db.commit()
    db.add(model(**values))
    with pytest.raises(IntegrityError):
        db.commit()


def location(item, **values):
    now = utcnow()
    return UserLocation(
        user_id=item.user_id,
        **{
            "latitude": Decimal("-23.55"),
            "longitude": Decimal("-46.63"),
            "recorded_at": now,
            "expires_at": now + timedelta(hours=1),
            **values,
        },
    )


def test_one_location_can_be_replaced_without_history(db):
    item = profile(db)
    item.nearby_enabled = True
    item.location = location(item)
    db.commit()
    item.location.latitude = Decimal("-23.56")
    db.commit()
    db.expire_all()
    assert item.location.latitude == Decimal("-23.56")
    assert db.scalar(select(func.count()).select_from(UserLocation)) == 1
    db.add(location(item))
    with pytest.raises(IntegrityError):
        db.commit()


@pytest.mark.parametrize(
    "values",
    [
        {"latitude": Decimal("90.01")},
        {"longitude": Decimal("-180.01")},
        {"latitude": Decimal("-23.551234")},
        {"longitude": Decimal("-46.631")},
        {"expires_at": utcnow() - timedelta(hours=1)},
    ],
)
def test_invalid_or_precise_location_rejected(db, values):
    db.add(location(profile(db), **values))
    with pytest.raises(IntegrityError):
        db.commit()


def test_deleting_user_removes_social_data_but_preserves_other_profile(db):
    ana, bia = profile(db), profile(db, "bia")
    db.add_all(
        [
            UserFollow(follower_id=ana.user_id, following_id=bia.user_id),
            UserFollow(follower_id=bia.user_id, following_id=ana.user_id),
            UserBlock(blocker_id=ana.user_id, blocked_id=bia.user_id),
            UserBlock(blocker_id=bia.user_id, blocked_id=ana.user_id),
            location(ana),
        ]
    )
    db.commit()
    db.delete(db.get(User, ana.user_id))
    db.commit()
    db.expire_all()
    for model in (UserFollow, UserBlock, UserLocation):
        assert db.scalar(select(func.count()).select_from(model)) == 0
    assert db.scalar(select(func.count()).select_from(UserProfile)) == 1
    assert db.get(UserProfile, bia.id) is not None
