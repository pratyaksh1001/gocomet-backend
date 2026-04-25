from sqlalchemy import String, ForeignKey, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, mapped_column, relationship
from database import engine


# ✅ Base
class Base(DeclarativeBase):
    pass


# 👤 USER
class User(Base):
    __tablename__ = "user"

    email = mapped_column(String, primary_key=True, index=True)
    username = mapped_column(String, nullable=False)
    password = mapped_column(String, nullable=False)

    # 🔗 Relationships
    auctions = relationship(
        "Auction",
        back_populates="owner",
        cascade="all, delete-orphan"
    )

    bids = relationship(
        "Bids",
        back_populates="owner",
        cascade="all, delete-orphan"
    )


# 📦 AUCTION
class Auction(Base):
    __tablename__ = "auction"
    rfq_id = mapped_column(Integer, primary_key=True, autoincrement=True)
    rfq_name = mapped_column(String, nullable=False)
    owner_email = mapped_column(
        String,
        ForeignKey("user.email", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    start_time = mapped_column(DateTime, nullable=False)
    forced_close_time = mapped_column(DateTime, nullable=False)
    pickup_date = mapped_column(DateTime, nullable=False)
    extension_duration = mapped_column(Integer, nullable=False)
    status = mapped_column(Integer, nullable=False)
    owner = relationship("User", back_populates="auctions", lazy="joined")

    bids = relationship(
        "Bids",
        back_populates="auction",
        cascade="all, delete-orphan"
    )


# 💰 BIDS
class Bids(Base):
    __tablename__ = "bids"

    bid_id = mapped_column(Integer, primary_key=True, autoincrement=True)

    owner_email = mapped_column(
        String,
        ForeignKey("user.email", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    owner = relationship("User", back_populates="bids", lazy="joined")

    auction_id = mapped_column(
        Integer,
        ForeignKey("auction.rfq_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    auction = relationship("Auction", back_populates="bids", lazy="joined")
    bid_amount = mapped_column(Integer, nullable=False)
    bid_time = mapped_column(DateTime, nullable=False)
    transit_time = mapped_column(Integer, nullable=False)
    freight_charges = mapped_column(Integer, nullable=False)
    origin_charges = mapped_column(Integer, nullable=False)
    destination_charges = mapped_column(Integer, nullable=False)
    validity_period = mapped_column(DateTime, nullable=False)



Base.metadata.create_all(bind=engine)