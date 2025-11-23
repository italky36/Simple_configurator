from typing import List, Optional

from sqlalchemy.orm import Session

from . import models


def get_coffee_machines(db: Session, skip: int = 0, limit: int = 100) -> List[models.CoffeeMachine]:
    return db.query(models.CoffeeMachine).offset(skip).limit(limit).all()


def get_coffee_machine(db: Session, machine_id: int) -> Optional[models.CoffeeMachine]:
    return db.query(models.CoffeeMachine).filter(models.CoffeeMachine.id == machine_id).first()


def get_coffee_machine_by_model(db: Session, model: str) -> Optional[models.CoffeeMachine]:
    return db.query(models.CoffeeMachine).filter(models.CoffeeMachine.model == model).first()


def get_coffee_machine_by_signature(
    db: Session,
    model: Optional[str],
    frame: Optional[str],
    frame_color: Optional[str],
    refrigerator: Optional[str],
    terminal: Optional[str],
) -> Optional[models.CoffeeMachine]:
    return (
        db.query(models.CoffeeMachine)
        .filter(
            models.CoffeeMachine.model == model,
            models.CoffeeMachine.frame == frame,
            models.CoffeeMachine.frame_color == frame_color,
            models.CoffeeMachine.refrigerator == refrigerator,
            models.CoffeeMachine.terminal == terminal,
        )
        .first()
    )


def get_models(db: Session) -> List[str]:
    query = db.query(models.CoffeeMachine.model).distinct().filter(models.CoffeeMachine.model.isnot(None))
    return [row[0] for row in query.all()]


def create_coffee_machine(db: Session, machine_data: dict) -> models.CoffeeMachine:
    db_machine = models.CoffeeMachine(**machine_data)
    db.add(db_machine)
    db.commit()
    db.refresh(db_machine)
    return db_machine


def update_coffee_machine(db: Session, machine_id: int, machine_data: dict) -> Optional[models.CoffeeMachine]:
    machine = get_coffee_machine(db, machine_id)
    if not machine:
        return None
    for key, value in machine_data.items():
        setattr(machine, key, value)
    db.commit()
    db.refresh(machine)
    return machine


def delete_coffee_machine(db: Session, machine_id: int) -> bool:
    machine = get_coffee_machine(db, machine_id)
    if not machine:
        return False
    db.delete(machine)
    db.commit()
    return True


# Device specs CRUD
def get_specs(db: Session, category: Optional[str] = None) -> List[models.DeviceSpec]:
    query = db.query(models.DeviceSpec)
    if category:
        query = query.filter(models.DeviceSpec.category == category)
    return query.all()


def get_spec(db: Session, spec_id: int) -> Optional[models.DeviceSpec]:
    return db.query(models.DeviceSpec).filter(models.DeviceSpec.id == spec_id).first()


def get_spec_by_name(db: Session, category: str, name: str) -> Optional[models.DeviceSpec]:
    return (
        db.query(models.DeviceSpec)
        .filter(models.DeviceSpec.category == category, models.DeviceSpec.name == name)
        .first()
    )


def create_spec(db: Session, spec_data: dict) -> models.DeviceSpec:
    spec = models.DeviceSpec(**spec_data)
    db.add(spec)
    db.commit()
    db.refresh(spec)
    return spec


def update_spec(db: Session, spec_id: int, spec_data: dict) -> Optional[models.DeviceSpec]:
    spec = get_spec(db, spec_id)
    if not spec:
        return None
    for k, v in spec_data.items():
        setattr(spec, k, v)
    db.commit()
    db.refresh(spec)
    return spec


def delete_spec(db: Session, spec_id: int) -> bool:
    spec = get_spec(db, spec_id)
    if not spec:
        return False
    db.delete(spec)
    db.commit()
    return True
