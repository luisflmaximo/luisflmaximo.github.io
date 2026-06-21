@echo off
title Instagram Autofill Tools - Processamento Browser
cls

echo ======================================================================
echo          INSTAGRAM AUTOFILL TOOLS - PROCESSAMENTO BROWSER
echo ======================================================================
echo.
echo IMPORTANTE: Por favor, garante que o teu browser Brave esta FECHADO.
echo O script vai abrir o Brave de forma automatica e visivel para ti.
echo Iras ver o browser a navegar nos teus guardados, extrair as imagens
echo e a desmarcar (Unsave) os posts no ecra em tempo real!
echo.
echo Pressiona qualquer tecla quando o Brave estiver fechado para iniciar...
pause > nul

echo.
echo A iniciar o processamento completo via Playwright...
python -u "%~dp0autofill.py" --username luisflmaximo

echo.
echo ======================================================================
echo                    PROCESSO CONCLUIDO COM SUCESSO!
echo ======================================================================
echo Podes reabrir o teu browser Brave agora normalmente.
echo.
pause
