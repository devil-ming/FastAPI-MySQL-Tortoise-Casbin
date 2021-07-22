"""
URL视图处理
"""
from typing import List
from datetime import timedelta

from fastapi import APIRouter, Depends, status, HTTPException, Request
from fastapi.security.oauth2 import OAuth2PasswordRequestForm

from . import crud, schema, model
from core.config import settings
from utils.response_code import ResultResponse
from utils import logger
from utils.utils import verify_password
from auth.auth import create_access_token
from auth.auth_casbin import Authority, get_casbin

from apps import user

router = APIRouter()


@router.post("/login",
             summary="用户登录认证",
             response_model=ResultResponse[schema.Token])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    通过用户名和密码登录获取 token 值
    :param form_data:
    :return:
    """
    # 验证用户
    user = await crud.get_user_by_name(username=form_data.username)
    if not user:
        logger.info(
            f"用户名认证错误: username:{form_data.username} password:{form_data.password}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='username or password error')

    # 验证密码
    if not verify_password(form_data.password, user.password):
        logger.info(
            f"用户密码错误: username:{form_data.username} password:{form_data.password}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='username or password error')

    # 登录成功后返回token
    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(subject=user.username,
                                       expires_delta=access_token_expires)

    return ResultResponse[schema.Token](result={
        'access_token': access_token,
        'token_type': 'bearer'
    })


@router.post('/register',
             summary='用户注册',
             description='注册新用户',
             response_model=ResultResponse[model.UserOut])
async def register(user: schema.UserCreate):
    user = await crud.create_user(user)
    return ResultResponse[model.UserOut](result=user)


@router.get("/info",
            summary="获取当前用户信息",
            name="获取当前用户信息",
            response_model=ResultResponse[model.UserOut])
async def get_user_info(request: Request):
    return ResultResponse[model.UserOut](result=request.state.user)


@router.get('/list',
            summary='获取用户列表',
            description='获取用户列表',
            response_model=ResultResponse[List[model.UserOut]])
async def get_user_list():
    user_list = await crud.get_user_list()
    return ResultResponse[List[model.UserOut]](result=user_list)


@router.post('/add/role',
             summary='添加角色',
             name='添加角色',
             response_model=ResultResponse[model.RoleCreate],
             dependencies=[Depends(Authority('role,add'))])
async def add_role(role: model.RoleOut):
    role = crud.create_role(role)
    return ResultResponse[model.RoleOut](result=role)


@router.post('/del/role',
             summary='删除角色',
             name='删除角色',
             response_model=ResultResponse[str],
             dependencies=[Depends(Authority('role,del'))])
async def del_role(request: Request, role_name: str):
    role = await crud.get_role_by_name(role_name)
    if not role:
        return ResultResponse[str](message='角色已删除')
    await role.delete()

    # 删除 casbin 的角色权限
    e = await get_casbin()
    e.delete_role_for_user(request.state.user.username, role.name)

    return ResultResponse[str](message='角色已删除')