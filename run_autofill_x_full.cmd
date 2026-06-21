@echo off
title X Bookmarks Autofill Tools - Processamento Browser
cls

echo ======================================================================
echo             X BOOKMARKS AUTOFILL TOOLS - PROCESSAMENTO BROWSER
echo ======================================================================
echo.
echo IMPORTANTE: Por favor, garante que o teu browser Brave esta FECHADO.
echo O script vai abrir o Brave de forma automatica e visivel para ti.
echo Iras ver o browser a navegar nos teus marcadores do X, extrair dados,
echo descarregar imagens e a remover os marcadores (Unsave) no ecra!
echo.
echo Pressiona qualquer tecla quando o Brave estiver fechado para iniciar...
pause > nul

echo.
echo A iniciar o processamento completo do X via Playwright...
python -u "%~dp0autofill_x.py"

echo.
echo ======================================================================
echo                    PROCESSO CONCLUIDO COM SUCESSO!
echo ======================================================================
echo Podes reabrir o teu browser Brave agora normalmente.
echo.
pause
