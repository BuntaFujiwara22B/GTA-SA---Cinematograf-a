"""IDs y números de captura facilitados por el usuario, sin inferir el Model por el orden."""
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FOTOS=Path(r'C:\Users\Danilo\Pictures\Screenshots')
VEHICULOS='''1477 420 taxi
1478 596 copcarla
1479 416 ambulan
1480 407 firetruk
1481 408 trash
1482 431 bus
1483 531 tractor
1484 532 combine
1485 495 sandking
1487 411 infernus
1488 470 patriot
1489 468 sanchez
1490 481 bmx
1491 405 sentinel
1492 426 premier
1493 421 washing
1494 445 admiral
1495 492 greenwoo
1496 419 esperant
1497 529 willard
1498 526 fortune
1499 409 stretch
1500 400 landstal
1501 489 rancher
1502 579 huntley
1503 429 banshee
1504 415 cheetah
1505 402 buffalo
1506 560 sultan
1507 562 elegy
1508 559 jester
1509 506 supergt
1510 412 voodoo
1511 576 tornado
1512 536 blade
1513 534 remingtn
1514 535 slamvan
1515 413 pony
1516 482 burrito
1518 414 mule
1519 403 linerun
1520 455 flatbed
1521 525 towtruck
1522 582 newsvan
1524 423 mrwhoop
1525 597 copcarsf
1526 598 copcarvg
1527 599 copcarru
1528 601 swatvan
1529 490 fbiranch
1530 427 enforcer
1531 544 firela
1532 432 rhino
1533 433 barracks
1534 461 pcj600
1535 462 faggio
1536 463 freeway
1537 586 wayfarer
1538 522 nrg500
1539 471 quad
1541 523 copbike
1542 510 mtbike
1543 457 caddy
1544 444 monster
1545 571 kart
1546 572 mower'''
OBJETOS='''1605 620 veg_palm04 veg
1606 648 veg_palm01 veg
1607 652 sjmpalmbig veg
1608 657 pinetree02 veg
1609 664 firtree2 veg
1610 693 sm_redwood_ veg
1611 615 veg_tree3 veg
1612 713 veg_bevtree1 veg
1613 763 Ash1_hi veg
1614 651 sjmcacti1 veg
1615 677 sm_des_agave1 veg
1616 702 sm_tumbleweed veg
1617 759 sm_bush_large_1 veg
1618 644 pot_02 veg
1619 741 pot_01 veg
1620 1702 kb_couch06 mueble
1621 1753 SWANK_COUCH_1 mueble
1622 1756 LOW_COUCH_4 mueble
1623 1735 CJ_EASYCHAIR1 mueble
1624 1704 kb_chair03 mueble
1625 1714 kb_swivelchair1 mueble
1626 1739 SWANK_DIN_CHAIR_5 mueble
1627 1737 MED_DINNING_5 mueble
1628 1745 MED_BED_3 mueble
1629 1793 LOW_BED_2 mueble
1630 1771 CJ_bunk_bed1 mueble
1631 1749 MED_TV_3 mueble
1632 1751 objeto_1751 mueble
1633 1742 Med_BOOKSHELF mueble
1634 1743 MED_CABINET_3 mueble
1635 1732 CJ_Juke_Box mueble
1636 1733 CJ_WASHINGMAC mueble
1637 1780 CJ_THIN_FRIGE mueble
1638 1773 CJ_COOKER2 mueble
1639 1775 CJ_SPRUNK1 mueble
1640 1776 CJ_CANDYVENDOR mueble
1641 1772 CJ_HOT_DOG1 mueble
1642 932 H_WHEELCHAIR mueble
1643 916 FRUITCRATE2 ind
1644 935 CJ_Drum ind
1645 918 CJ_FLAME_Drum ind
1646 930 O2_Bottles ind
1647 929 GENERATOR ind
1648 964 CJ_METAL_CRATE ind
1649 960 CJ_ARM_CRATE ind
1650 2768 CJ_CB_BURG comida
1651 2212 burgerhigh comida
1652 2217 cluckhigh comida
1653 2220 pizzahigh comida
1654 2222 rustyhigh comida
1655 1282 Barrierm policia
1656 1427 CJ_ROADBARRIER policia
1657 1459 DYN_ROADBARRIER_6 policia
1659 2977 kmilitary_crate militar
1660 2040 AMMO_BOX_M1 militar
1661 3082 ammo_capsule militar
1662 2985 minigun_base militar'''


def importar():
    for tipo,tabla,carpeta in [('vehicles',VEHICULOS,'Vehículos'),('objects',OBJETOS,'Objetos')]:
        destino=ROOT/'assets'/tipo;destino.mkdir(exist_ok=True)
        filas=[]
        for linea in tabla.splitlines():
            campos=linea.split();captura,modelo=map(int,campos[:2]);nombre=campos[2]
            foto=FOTOS/carpeta/f'Captura de pantalla ({captura}).png'
            relativa=f'{tipo}/{modelo}_{nombre}.png'
            if foto.exists():shutil.copy2(foto,ROOT/'assets'/relativa)
            filas.append(dict(model_id=modelo,nombre=nombre,categoria=campos[3] if len(campos)>3 else 'vehiculo',
                captura=captura,foto=relativa,disponible=foto.exists(),origen='Tabla explícita del usuario'))
        (ROOT/'assets'/f'{tipo}_catalogo.json').write_text(json.dumps(filas,ensure_ascii=False,indent=2),encoding='utf-8')
        print(tipo,len(filas),'con foto',sum(r['disponible'] for r in filas))


if __name__=='__main__':importar()
